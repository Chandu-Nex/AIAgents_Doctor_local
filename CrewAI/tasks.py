from crewai import Task

def create_tasks():
    task_extract_info = Task(
        description=(
            "Extract key medical information from the input: {user_input} and chunk API data: {chunkdata}. "
            "Call the chunk API at http://10.0.1.52:8000/chunkapi with the user input. "
            "Identify symptoms, duration, severity, and context. "
            "Store the input and API response in Redis and Postgres. "
            "Return a JSON object with fields: symptoms (list), duration (string), severity (string), context (string), chunkdata (string)."
        ),
        expected_output="A JSON object with extracted medical information and chunk data.",
        async_execution=False
    )

    task_analyze_symptoms = Task(
        description=(
            "Analyze the extracted information: {extracted_info}. Identify symptom patterns and potential causes. "
            "If the information is insufficient, request clarification from the Information Agent. "
            "Store the interaction in Redis and Postgres. Return the analysis or a clarification request."
        ),
        expected_output="Symptom analysis or a clarification request.",
        context=[task_extract_info]
    )

    task_reason_diagnosis = Task(
        description=(
            "Reason possible diagnoses based on symptom analysis: {symptom_analysis}. "
            "If the analysis is unclear, request clarification from the Symptom Analyzer. "
            "Store the interaction in Redis and Postgres. "
            "Return a list of differential diagnoses with reasoning."
        ),
        expected_output="List of differential diagnoses or a clarification request.",
        context=[task_analyze_symptoms]
    )

    task_suggest_treatment = Task(
        description=(
            "Suggest treatments for the diagnoses: {diagnoses}. Store the interaction in Redis and Postgres. "
            "Return treatment suggestions, precautions, and advice."
        ),
        expected_output="Treatment suggestions, precautions, and advice.",
        context=[task_reason_diagnosis]
    )

    task_judge = Task(
        description=(
            "Validate the output from task: {task_name} with content: {task_output} against user input: {user_input}. "
            "Check for medical accuracy, relevance, and safety. "
            "Store the validation attempt in Redis and Postgres. "
            "If invalid, return a JSON object with an error message and suggested corrections. "
            "If valid, return a JSON object with the validated output."
        ),
        expected_output="A JSON object with validated output or an error message."
    )

    task_communicate = Task(
        description=(
            "Format the validated information: {validated_output} into a clear, empathetic, user-friendly response. "
            "If the output contains an error or is empty, return: "
            "'We couldn't process your request due to insufficient information. Please provide more details about your symptoms.' "
            "Otherwise, summarize symptoms, diagnoses, treatments, and precautions in plain language."
        ),
        expected_output="A user-friendly response or a message requesting more details.",
        context=[task_judge]
    )

    return {
        'task_extract_info': task_extract_info,
        'task_analyze_symptoms': task_analyze_symptoms,
        'task_reason_diagnosis': task_reason_diagnosis,
        'task_suggest_treatment': task_suggest_treatment,
        'task_judge': task_judge,
        'task_communicate': task_communicate
    }