from uuid import uuid4
import json
from postgres_utils import log_communication, update_communication, log_verification
from redis_utils import RedisStorage

redis_storage = RedisStorage()

# Helper function to format task description
def format_task_description(task, inputs):
    description = task.description
    replaced_keys = []
    for key, value in inputs.items():
        placeholder = '{' + key + '}'
        if placeholder in description:
            description = description.replace(placeholder, str(value))
            replaced_keys.append(key)
    # Append special unreplaced keys
    for key, value in inputs.items():
        if key not in replaced_keys:
            if key == 'corrections':
                description += f"\nApply the following corrections: {value}"
            elif key == 'clarification_request':
                description += f"\nAddress this clarification request: {value}"
            elif key == 'clarification_response':
                description += f"\nUse this clarification response: {value}"
    return description

# Custom function to handle task execution with validation and retries
def execute_task_with_validation(task, inputs, session_id, health_query_id, user_input, task_judge, max_retries=3):
    attempt = 0
    current_inputs = inputs.copy()
    task_name = task.agent.role
    original_description = task.description  # Save original to reset if needed
    while attempt < max_retries:
        # Format the task description
        task.description = format_task_description(task, current_inputs)

        # Execute the task using the agent
        try:
            task_output = task.agent.execute_task(task=task)
        except Exception as e:
            task.description = original_description
            return f"Error in {task_name}: {str(e)}"

        # Reset description
        task.description = original_description

        # Store task output in Redis
        redis_storage.save(
            value=str(task_output),
            metadata={'session_id': session_id, 'type': task_name.lower().replace(' ', '_'), 'user_id': 1},
            agent=task_name
        )

        # Log task output in Postgres
        comm_id = log_communication(
            sender='user' if task_name == 'Information Agent' else task_name,
            receiver='Judge Agent',
            input_msg=str(current_inputs),
            session_id=uuid4(),
            health_query_response_id=health_query_id
        )

        # Validate with Judge Agent
        validation_inputs = {
            'task_name': task_name,
            'task_output': str(task_output),
            'user_input': user_input
        }
        judge_original_desc = task_judge.description
        task_judge.description = format_task_description(task_judge, validation_inputs)
        try:
            validation_result = task_judge.agent.execute_task(task=task_judge)
        except Exception as e:
            task_judge.description = judge_original_desc
            return f"Error in Judge Agent: {str(e)}"
        task_judge.description = judge_original_desc

        # Store validation attempt
        verification_id = log_verification(
            action_type='validate',
            entity_type=task_name.lower().replace(' ', '_'),
            entity_id=comm_id,
            old_data={'input': str(current_inputs)},
            new_data={'output': str(task_output)},
            details={'validation_result': validation_result},
            actor='Judge Agent',
            status='completed',
            session_id=uuid4(),
            agent_communication_id=comm_id
        )

        # Parse validation result
        try:
            validation_data = json.loads(validation_result) if isinstance(validation_result, str) else validation_result
            if 'error' in validation_data:
                attempt += 1
                # Update communication status
                update_communication(comm_id, output_msg=str(task_output), status='failed')
                if attempt == max_retries:
                    return f"Max retries reached for {task_name}: {validation_data['error']}"
                # Update inputs with suggested corrections
                current_inputs.update({'corrections': validation_data.get('suggested_corrections', '')})
                continue
            else:
                update_communication(comm_id, output_msg=str(task_output), status='completed')
                return task_output
        except json.JSONDecodeError:
            return f"Error parsing validation result for {task_name}"

    return f"Validation failed for {task_name}"

# Custom function for back-and-forth communication
def execute_task_with_clarification(task, inputs, previous_task, session_id, health_query_id, user_input, task_judge):
    task_name = task.agent.role
    original_description = task.description
    # Execute with validation
    result = execute_task_with_validation(task, inputs, session_id, health_query_id, user_input, task_judge)
    task.description = original_description  # Reset
    
    # Check if clarification is needed
    if isinstance(result, str) and 'clarification request' in result.lower():
        if previous_task:
            # Log clarification request
            comm_id = log_communication(
                sender=task_name,
                receiver=previous_task.agent.role,
                input_msg=result,
                session_id=uuid4(),
                health_query_response_id=health_query_id
            )
            redis_storage.save(
                value=result,
                metadata={'session_id': session_id, 'type': 'clarification_request', 'user_id': 1},
                agent=task_name
            )
            # Re-run previous task with clarification request
            clarification_inputs = inputs.copy()
            clarification_inputs['clarification_request'] = result
            prev_original_desc = previous_task.description
            clarification_result = execute_task_with_validation(previous_task, clarification_inputs, session_id, health_query_id, user_input, task_judge)
            previous_task.description = prev_original_desc
            
            # Re-run current task with clarification
            new_inputs = inputs.copy()
            new_inputs['clarification_response'] = clarification_result
            task.description = original_description  # Ensure reset
            return execute_task_with_validation(task, new_inputs, session_id, health_query_id, user_input, task_judge)
        else:
            return "No previous task available for clarification"
    return result

def extract_parsed_content_from_llm_response(llm_response):
    """
    Extract and parse JSON content from LLM response.
    Returns a dictionary with parsed content or raw response if parsing fails.
    """
    import json
    import re
    
    parsed_content = {}
    
    try:
        if isinstance(llm_response, str):
            # Try to find JSON patterns in the response
            # Look for complete JSON objects
            json_patterns = [
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON
                r'\{[^}]*\}',  # Simple JSON
                r'\[[^\]]*\]'  # JSON arrays
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, llm_response, re.DOTALL)
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict) and parsed:
                            # Merge with existing parsed content
                            parsed_content.update(parsed)
                        elif isinstance(parsed, list) and parsed:
                            parsed_content['extracted_list'] = parsed
                    except json.JSONDecodeError:
                        continue
            
            # If no JSON found, store as raw response
            if not parsed_content:
                parsed_content = {
                    'raw_response': llm_response,
                    'response_type': 'text'
                }
            else:
                parsed_content['response_type'] = 'structured'
                parsed_content['raw_response'] = llm_response
                
        else:
            # Handle non-string responses
            parsed_content = {
                'raw_response': str(llm_response),
                'response_type': 'non_string'
            }
            
    except Exception as e:
        parsed_content = {
            'raw_response': str(llm_response),
            'error': str(e),
            'response_type': 'error'
        }
    
    return parsed_content