import requests
from crewai import LLM
from flask import Flask, request, render_template, jsonify
from uuid import uuid4
import json
from redis_utils import RedisStorage
from postgres_utils import log_communication, update_communication, log_verification, log_health_query, update_health_query_response, store_structured_medical_data
from agents import create_agents
from tasks import create_tasks
from execution_utils import format_task_description, execute_task_with_validation, execute_task_with_clarification, extract_parsed_content_from_llm_response
from llm import MedGemmaLLM

app = Flask(__name__)

# Initialize Redis storage
redis_storage = RedisStorage()

# In-memory session storage (in production, use Redis or database)
session_store = {}

def get_session_data(session_id):
    """Get session data from storage"""
    return session_store.get(session_id, {
        'messages': [],
        'context': {},
        'created_at': None
    })

def save_session_data(session_id, data):
    """Save session data to storage"""
    session_store[session_id] = data

def build_conversation_context(conversation_history, current_input):
    """Build context from conversation history"""
    context = {
        'previous_symptoms': [],
        'previous_diagnoses': [],
        'previous_treatments': [],
        'patient_concerns': [],
        'medical_history': [],
        'current_medications': [],
        'allergies': [],
        'lifestyle_factors': []
    }
    
    # Process conversation history to extract relevant information
    for message in conversation_history:
        if message['role'] == 'user':
            # Extract key information from user messages
            content = message['content'].lower()
            
            # Extract symptoms
            if any(word in content for word in ['pain', 'ache', 'hurt', 'symptom', 'feeling']):
                context['previous_symptoms'].append(message['content'])
            
            # Extract medical history
            if any(word in content for word in ['history', 'diagnosed', 'condition', 'disease']):
                context['medical_history'].append(message['content'])
            
            # Extract medications
            if any(word in content for word in ['medication', 'medicine', 'pill', 'prescription']):
                context['current_medications'].append(message['content'])
            
            # Extract allergies
            if any(word in content for word in ['allergy', 'allergic', 'reaction']):
                context['allergies'].append(message['content'])
            
            # Extract lifestyle factors
            if any(word in content for word in ['exercise', 'diet', 'smoking', 'alcohol', 'stress']):
                context['lifestyle_factors'].append(message['content'])
        
        elif message['role'] == 'assistant':
            # Extract diagnoses and treatments from assistant responses
            content = message['content'].lower()
            
            if any(word in content for word in ['diagnosis', 'condition', 'disease']):
                context['previous_diagnoses'].append(message['content'])
            
            if any(word in content for word in ['treatment', 'medication', 'therapy', 'recommendation']):
                context['previous_treatments'].append(message['content'])
    
    # Add current input to context
    context['current_input'] = current_input
    
    return context

def format_conversation_for_ai(conversation_history, current_input):
    """Format conversation history for AI processing"""
    if not conversation_history:
        return f"Current user input: {current_input}"
    
    formatted_history = "Previous conversation:\n"
    for i, message in enumerate(conversation_history[-10:], 1):  # Last 10 messages for context
        role = "Patient" if message['role'] == 'user' else "Dr. AI"
        formatted_history += f"{i}. {role}: {message['content']}\n"
    
    formatted_history += f"\nCurrent user input: {current_input}"
    return formatted_history

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_input = request.form.get('user_input', '').strip()
        session_id = request.form.get('session_id', str(uuid4()))
        conversation_history = request.form.get('conversation_history', '[]')
        
        if not user_input:
            return render_template('index.html', result="Please enter a message.", session_id=session_id)

        try:
            # Parse conversation history
            conversation_data = json.loads(conversation_history) if conversation_history else []
            
            # Get session data
            session_data = get_session_data(session_id)
            
            # Build conversation context
            context = build_conversation_context(conversation_data, user_input)
            
            # Format conversation for AI
            formatted_conversation = format_conversation_for_ai(conversation_data, user_input)
            
            # Store user input in Postgres (HealthQueryResponse)
            try:
                health_query_id = log_health_query(
                    user_id=1, 
                    session_id=session_id, 
                    input_text=user_input, 
                    status='pending'
                )
            except Exception as e:
                return render_template('index.html', result=f"Error logging health query: {str(e)}", session_id=session_id)

            # Store user input in Redis with conversation context
            try:
                redis_storage.save(
                    value=json.dumps({
                        'user_input': user_input,
                        'conversation_context': context,
                        'formatted_conversation': formatted_conversation
                    }),
                    metadata={
                        'session_id': session_id, 
                        'type': 'user_input_with_context', 
                        'user_id': 1
                    },
                    agent='user'
                )
            except Exception as e:
                return render_template('index.html', result=f"Error storing in Redis: {str(e)}", session_id=session_id)

            # Step 1: Instantiate MedGemma LLM
            custom_llm = LLM(
                model="openai/medgemma-4b-it",
                base_url="http://10.0.2.32:9001/v1",
                api_key="lm-studio"
            )

            # Define Agents
            agents = create_agents(custom_llm)

            # Define Tasks
            tasks = create_tasks()

            task_extract_info = tasks['task_extract_info']
            task_extract_info.agent = agents['information_agent']

            task_analyze_symptoms = tasks['task_analyze_symptoms']
            task_analyze_symptoms.agent = agents['symptom_analyzer']

            task_reason_diagnosis = tasks['task_reason_diagnosis']
            task_reason_diagnosis.agent = agents['diagnosis_reasoner']

            task_suggest_treatment = tasks['task_suggest_treatment']
            task_suggest_treatment.agent = agents['treatment_suggester']

            task_judge = tasks['task_judge']
            task_judge.agent = agents['judge_agent']

            task_communicate = tasks['task_communicate']
            task_communicate.agent = agents['communicator']

            # Process tasks with conversation context
            try:
                # Call chunk API with conversation context
                chunk_url = "http://10.0.1.52:8000/chunkapi"
                try:
                    chunk_response = requests.post(chunk_url, json={
                        "text": formatted_conversation
                    })
                    chunk_response.raise_for_status()
                    chunk_data = chunk_response.text
                except Exception as e:
                    return render_template('index.html', result=f"Error calling chunk API: {str(e)}", session_id=session_id)

                # Execute Information Agent with conversation context
                extract_info_result = execute_task_with_validation(
                    task_extract_info,
                    {
                        'user_input': formatted_conversation, 
                        'chunkdata': chunk_data,
                        'conversation_context': context
                    },
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(extract_info_result):
                    return render_template('index.html', result=extract_info_result, session_id=session_id)

                # Execute Symptom Analyzer with conversation context
                symptom_analysis_result = execute_task_with_clarification(
                    task_analyze_symptoms,
                    {
                        'extracted_info': extract_info_result,
                        'conversation_context': context
                    },
                    task_extract_info,
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(symptom_analysis_result):
                    return render_template('index.html', result=symptom_analysis_result, session_id=session_id)

                # Execute Diagnosis Reasoner with conversation context
                diagnosis_result = execute_task_with_clarification(
                    task_reason_diagnosis,
                    {
                        'symptom_analysis': symptom_analysis_result,
                        'conversation_context': context
                    },
                    task_analyze_symptoms,
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(diagnosis_result):
                    return render_template('index.html', result=diagnosis_result, session_id=session_id)

                # Execute Treatment Suggester with conversation context
                treatment_result = execute_task_with_validation(
                    task_suggest_treatment,
                    {
                        'diagnoses': diagnosis_result,
                        'conversation_context': context
                    },
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(treatment_result):
                    return render_template('index.html', result=treatment_result, session_id=session_id)

                # Execute Communicator with conversation context
                communicate_inputs = {
                    'validated_output': treatment_result,
                    'conversation_context': context,
                    'conversation_history': conversation_data
                }
                communicate_original_desc = task_communicate.description
                task_communicate.description = format_task_description(task_communicate, communicate_inputs)
                
                try:
                    final_result = task_communicate.agent.execute_task(task=task_communicate)
                    
                    # Extract and parse JSON content from LLM response
                    parsed_content = extract_parsed_content_from_llm_response(final_result)
                    
                    # Store parsed content in Redis for further processing
                    redis_storage.save(
                        value=json.dumps(parsed_content),
                        metadata={
                            'session_id': session_id, 
                            'type': 'parsed_llm_response', 
                            'user_id': 1
                        },
                        agent='communicator'
                    )
                    
                except Exception as e:
                    final_result = f"Error in Communicator: {str(e)}"
                    parsed_content = {'error': str(e)}
                
                task_communicate.description = communicate_original_desc
                
                if 'Error' in str(final_result):
                    return render_template('index.html', result=final_result, session_id=session_id)

                # Update health query response in Postgres
                update_health_query_response(session_id, final_result, status='completed')
                
                # Store structured medical data in database
                try:
                    structured_data_id = store_structured_medical_data(session_id, health_query_id, parsed_content)
                    print(f"Structured medical data stored with ID: {structured_data_id}")
                except Exception as e:
                    print(f"Error storing structured medical data: {str(e)}")
                
                # Log the parsed content separately for structured data access
                try:
                    log_communication(
                        sender='communicator',
                        receiver='database',
                        input_msg=json.dumps(parsed_content),
                        output_msg=final_result,
                        session_id=uuid4(),
                        health_query_response_id=health_query_id
                    )
                except Exception as e:
                    print(f"Error logging parsed content: {str(e)}")

                # Update session data
                session_data['messages'] = conversation_data + [
                    {'role': 'user', 'content': user_input, 'timestamp': 'now'},
                    {'role': 'assistant', 'content': final_result, 'timestamp': 'now'}
                ]
                session_data['context'] = context
                save_session_data(session_id, session_data)

                return render_template('index.html', result=final_result, session_id=session_id)

            except Exception as e:
                return render_template('index.html', result=f"Error in crew processing: {str(e)}", session_id=session_id)

        except json.JSONDecodeError:
            return render_template('index.html', result="Error parsing conversation history", session_id=session_id)
        except Exception as e:
            return render_template('index.html', result=f"Error processing request: {str(e)}", session_id=session_id)

    # GET request - show the chat interface
    session_id = str(uuid4())
    return render_template('index.html', session_id=session_id)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    """API endpoint for AJAX chat requests"""
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        session_id = data.get('session_id', str(uuid4()))
        conversation_history = data.get('conversation_history', [])
        
        if not user_input:
            return jsonify({'error': 'Please enter a message.'})

        try:
            # Parse conversation history
            conversation_data = conversation_history if isinstance(conversation_history, list) else []
            
            # Get session data
            session_data = get_session_data(session_id)
            
            # Build conversation context
            context = build_conversation_context(conversation_data, user_input)
            
            # Format conversation for AI
            formatted_conversation = format_conversation_for_ai(conversation_data, user_input)
            
            # Store user input in Postgres (HealthQueryResponse)
            try:
                health_query_id = log_health_query(
                    user_id=1, 
                    session_id=session_id, 
                    input_text=user_input, 
                    status='pending'
                )
            except Exception as e:
                return jsonify({'error': f"Error logging health query: {str(e)}"})

            # Store user input in Redis with conversation context
            try:
                redis_storage.save(
                    value=json.dumps({
                        'user_input': user_input,
                        'conversation_context': context,
                        'formatted_conversation': formatted_conversation
                    }),
                    metadata={
                        'session_id': session_id, 
                        'type': 'user_input_with_context', 
                        'user_id': 1
                    },
                    agent='user'
                )
            except Exception as e:
                return jsonify({'error': f"Error storing in Redis: {str(e)}"})

            # Instantiate MedGemma LLM
            custom_llm = LLM(
                model="openai/medgemma-4b-it",
                base_url="http://10.0.2.32:9001/v1",
                api_key="lm-studio"
            )

            # Define Agents
            agents = create_agents(custom_llm)

            # Define Tasks
            tasks = create_tasks()

            task_extract_info = tasks['task_extract_info']
            task_extract_info.agent = agents['information_agent']

            task_analyze_symptoms = tasks['task_analyze_symptoms']
            task_analyze_symptoms.agent = agents['symptom_analyzer']

            task_reason_diagnosis = tasks['task_reason_diagnosis']
            task_reason_diagnosis.agent = agents['diagnosis_reasoner']

            task_suggest_treatment = tasks['task_suggest_treatment']
            task_suggest_treatment.agent = agents['treatment_suggester']

            task_judge = tasks['task_judge']
            task_judge.agent = agents['judge_agent']

            task_communicate = tasks['task_communicate']
            task_communicate.agent = agents['communicator']

            # Process tasks with conversation context
            try:
                # Call chunk API with conversation context
                chunk_url = "http://10.0.1.52:8000/chunkapi"
                try:
                    chunk_response = requests.post(chunk_url, json={
                        "text": formatted_conversation
                    })
                    chunk_response.raise_for_status()
                    chunk_data = chunk_response.text
                except Exception as e:
                    return jsonify({'error': f"Error calling chunk API: {str(e)}"})

                # Execute Information Agent with conversation context
                extract_info_result = execute_task_with_validation(
                    task_extract_info,
                    {
                        'user_input': formatted_conversation, 
                        'chunkdata': chunk_data,
                        'conversation_context': context
                    },
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(extract_info_result):
                    return jsonify({'error': str(extract_info_result)})

                # Execute Symptom Analyzer with conversation context
                symptom_analysis_result = execute_task_with_clarification(
                    task_analyze_symptoms,
                    {
                        'extracted_info': extract_info_result,
                        'conversation_context': context
                    },
                    task_extract_info,
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(symptom_analysis_result):
                    return jsonify({'error': str(symptom_analysis_result)})

                # Execute Diagnosis Reasoner with conversation context
                diagnosis_result = execute_task_with_clarification(
                    task_reason_diagnosis,
                    {
                        'symptom_analysis': symptom_analysis_result,
                        'conversation_context': context
                    },
                    task_analyze_symptoms,
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(diagnosis_result):
                    return jsonify({'error': str(diagnosis_result)})

                # Execute Treatment Suggester with conversation context
                treatment_result = execute_task_with_validation(
                    task_suggest_treatment,
                    {
                        'diagnoses': diagnosis_result,
                        'conversation_context': context
                    },
                    session_id=session_id,
                    health_query_id=health_query_id,
                    user_input=user_input,
                    task_judge=task_judge
                )
                if 'Error' in str(treatment_result):
                    return jsonify({'error': str(treatment_result)})

                # Execute Communicator with conversation context
                communicate_inputs = {
                    'validated_output': treatment_result,
                    'conversation_context': context,
                    'conversation_history': conversation_data
                }
                communicate_original_desc = task_communicate.description
                task_communicate.description = format_task_description(task_communicate, communicate_inputs)
                
                try:
                    final_result = task_communicate.agent.execute_task(task=task_communicate)
                    
                    # Extract and parse JSON content from LLM response
                    parsed_content = extract_parsed_content_from_llm_response(final_result)
                    
                    # Store parsed content in Redis for further processing
                    redis_storage.save(
                        value=json.dumps(parsed_content),
                        metadata={
                            'session_id': session_id, 
                            'type': 'parsed_llm_response', 
                            'user_id': 1
                        },
                        agent='communicator'
                    )
                    
                except Exception as e:
                    final_result = f"Error in Communicator: {str(e)}"
                    parsed_content = {'error': str(e)}
                
                task_communicate.description = communicate_original_desc
                
                if 'Error' in str(final_result):
                    return jsonify({'error': str(final_result)})

                # Update health query response in Postgres
                update_health_query_response(session_id, final_result, status='completed')
                
                # Store structured medical data in database
                try:
                    structured_data_id = store_structured_medical_data(session_id, health_query_id, parsed_content)
                    print(f"Structured medical data stored with ID: {structured_data_id}")
                except Exception as e:
                    print(f"Error storing structured medical data: {str(e)}")
                
                # Log the parsed content separately for structured data access
                try:
                    log_communication(
                        sender='communicator',
                        receiver='database',
                        input_msg=json.dumps(parsed_content),
                        output_msg=final_result,
                        session_id=uuid4(),
                        health_query_response_id=health_query_id
                    )
                except Exception as e:
                    print(f"Error logging parsed content: {str(e)}")

                # Update session data
                session_data['messages'] = conversation_data + [
                    {'role': 'user', 'content': user_input, 'timestamp': 'now'},
                    {'role': 'assistant', 'content': final_result, 'timestamp': 'now'}
                ]
                session_data['context'] = context
                save_session_data(session_id, session_data)

                return jsonify({
                    'response': final_result,
                    'session_id': session_id,
                    'timestamp': 'now',
                    'parsed_content': parsed_content
                })

            except Exception as e:
                return jsonify({'error': f"Error in crew processing: {str(e)}"})

        except Exception as e:
            return jsonify({'error': f"Error processing request: {str(e)}"})
        
    except Exception as e:
        return jsonify({'error': f'Error processing request: {str(e)}'})

@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session data"""
    session_data = get_session_data(session_id)
    return jsonify(session_data)

@app.route('/api/session/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    """Clear session data"""
    if session_id in session_store:
        del session_store[session_id]
    return jsonify({'message': 'Session cleared'})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)