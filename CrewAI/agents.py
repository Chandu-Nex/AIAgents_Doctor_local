from crewai import Agent

def create_agents(custom_llm):
    information_agent = Agent(
        role='Information Agent',
        goal='Extract and organize key information from user input and chunk API, storing interactions.',
        backstory='You are an expert in parsing medical queries and coordinating with APIs.',
        llm=custom_llm,
        verbose=True
    )

    symptom_analyzer = Agent(
        role='Symptom Analyzer',
        goal='Analyze symptoms and request clarification if needed, storing interactions.',
        backstory='You specialize in symptom analysis and can request more details if needed.',
        llm=custom_llm,
        verbose=True
    )

    diagnosis_reasoner = Agent(
        role='Diagnosis Reasoner',
        goal='Reason possible diagnoses and request clarification if needed, storing interactions.',
        backstory='You are a diagnostic expert, ensuring clarity by coordinating with prior agents.',
        llm=custom_llm,
        verbose=True
    )

    treatment_suggester = Agent(
        role='Treatment Suggester',
        goal='Suggest treatments for diagnoses, storing interactions.',
        backstory='You provide evidence-based treatment suggestions.',
        llm=custom_llm,
        verbose=True
    )

    judge_agent = Agent(
        role='Judge Agent',
        goal='Validate agent outputs for accuracy and relevance, storing validation attempts.',
        backstory='You ensure medical accuracy and consistency, triggering retries if needed.',
        llm=custom_llm,
        verbose=True
    )

    communicator = Agent(
        role='Communicator',
        goal='Format validated information into a user-friendly response.',
        backstory='You translate complex medical information into clear language.',
        llm=custom_llm,
        verbose=True
    )

    return {
        'information_agent': information_agent,
        'symptom_analyzer': symptom_analyzer,
        'diagnosis_reasoner': diagnosis_reasoner,
        'treatment_suggester': treatment_suggester,
        'judge_agent': judge_agent,
        'communicator': communicator
    }