from fastapi import FastAPI, Query, HTTPException
from neo4j import GraphDatabase
from typing import List, Dict, Any
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Fetch Neo4j credentials
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


# ===== FastAPI App =====
app = FastAPI(title="Medical Knowledge Graph API")

# ===== Response Models =====
class Triple(BaseModel):
    subject: str
    predicate: str
    object: str

class GroupedData(BaseModel):
    disease: str
    symptoms: List[str]
    causes: List[str]
    precautions: List[str]
    drugs: List[str]
    drug_descriptions: List[str]

class SearchResponse(BaseModel):
    query: str
    grouped: GroupedData
    triples: List[Triple]


# ===== Neo4j Query Function =====
def retrieve_facts_and_grouped(tx, user_input: str) -> Dict[str, Any]:
    query = """
    // Disease-based search
    MATCH (d:Disease)
    WHERE toLower(d.name) CONTAINS toLower($input)
    OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
    OPTIONAL MATCH (d)-[:HAS_CAUSE]->(c:Cause)
    OPTIONAL MATCH (d)-[:HAS_PRECAUTION]->(p:Precaution)
    OPTIONAL MATCH (d)-[:TREATED_BY]->(dr:Drug)
    OPTIONAL MATCH (dr)-[:HAS_DESCRIPTION]->(desc:Description)
    RETURN d.name AS disease,
           collect(DISTINCT s.name) AS symptoms,
           collect(DISTINCT c.name) AS causes,
           collect(DISTINCT p.name) AS precautions,
           collect(DISTINCT dr.name) AS drugs,
           collect(DISTINCT desc.text) AS drug_descriptions

    UNION

    // Symptom-based search
    MATCH (s:Symptom)
    WHERE toLower(s.name) CONTAINS toLower($input)
    MATCH (d:Disease)-[:HAS_SYMPTOM]->(s)
    OPTIONAL MATCH (d)-[:HAS_CAUSE]->(c:Cause)
    OPTIONAL MATCH (d)-[:HAS_PRECAUTION]->(p:Precaution)
    OPTIONAL MATCH (d)-[:TREATED_BY]->(dr:Drug)
    OPTIONAL MATCH (dr)-[:HAS_DESCRIPTION]->(desc:Description)
    RETURN d.name AS disease,
           collect(DISTINCT s.name) AS symptoms,
           collect(DISTINCT c.name) AS causes,
           collect(DISTINCT p.name) AS precautions,
           collect(DISTINCT dr.name) AS drugs,
           collect(DISTINCT desc.text) AS drug_descriptions
    """
    result = tx.run(query, input=user_input)
    grouped_data = None
    triples = []

    for record in result:
        disease = record["disease"]

        symptoms = [s for s in record["symptoms"] if s]
        causes = [c for c in record["causes"] if c]
        precautions = [p for p in record["precautions"] if p]
        drugs = [d for d in record["drugs"] if d]
        drug_descriptions = [desc for desc in record["drug_descriptions"] if desc]

        # Grouped format (only one, assuming unique disease match)
        if not grouped_data:
            grouped_data = {
                "disease": disease,
                "symptoms": symptoms,
                "causes": causes,
                "precautions": precautions,
                "drugs": drugs,
                "drug_descriptions": drug_descriptions
            }

        # Triples
        for s in symptoms:
            triples.append({"subject": disease, "predicate": "HAS_SYMPTOM", "object": s})
        for c in causes:
            triples.append({"subject": disease, "predicate": "HAS_CAUSE", "object": c})
        for p in precautions:
            triples.append({"subject": disease, "predicate": "HAS_PRECAUTION", "object": p})
        for d in drugs:
            triples.append({"subject": disease, "predicate": "TREATED_BY", "object": d})
        for desc in drug_descriptions:
            triples.append({"subject": d, "predicate": "HAS_DESCRIPTION", "object": desc})

    return {"grouped": grouped_data, "triples": triples}


# ===== API Endpoint =====
@app.get("/knowledgegraphapi", response_model=SearchResponse)
def get_medical_kg_data(query: str = Query(..., description="Disease name or symptom")):
    try:
        with driver.session() as session:
            result = session.execute_read(retrieve_facts_and_grouped, query)

        if not result["grouped"]:
            raise HTTPException(status_code=404, detail="❌ No data found")

        return {
            "query": query,
            "grouped": result["grouped"],
            "triples": result["triples"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ===== Run the API =====
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
