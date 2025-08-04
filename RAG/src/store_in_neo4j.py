import torch
import torch.nn as nn
import torch.optim as optim
from neo4j import GraphDatabase
import argparse
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Fetch Neo4j credentials
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# ====== KG Embedding Models ======
class DistMult(nn.Module):
    def __init__(self, num_entities, num_relations, embedding_dim):
        super().__init__()
        self.entity_embedding = nn.Embedding(num_entities, embedding_dim)
        self.relation_embedding = nn.Embedding(num_relations, embedding_dim)

    def forward(self, h, r, t):
        return torch.sum(self.entity_embedding(h) * self.relation_embedding(r) * self.entity_embedding(t), dim=1)

class TransE(nn.Module):
    def __init__(self, num_entities, num_relations, embedding_dim):
        super().__init__()
        self.entity_embedding = nn.Embedding(num_entities, embedding_dim)
        self.relation_embedding = nn.Embedding(num_relations, embedding_dim)

    def forward(self, h, r, t):
        return -torch.norm(self.entity_embedding(h) + self.relation_embedding(r) - self.entity_embedding(t), p=1, dim=1)

# ====== Custom Neo4j Insert Logic (NoGAN) ======
def insert_triples(tx, disease):
    tx.run("MERGE (d:Disease {name: $name}) SET d.description = $description",
           name=disease["name"], description=disease["description"])

    for symptom in disease.get("symptoms", "").split(","):
        symptom = symptom.strip()
        if symptom:
            tx.run("""
            MERGE (s:Symptom {name: $symptom})
            MERGE (d:Disease {name: $name})
            MERGE (d)-[:HAS_SYMPTOM]->(s)
            """, name=disease["name"], symptom=symptom)

    if disease.get("cause"):
        tx.run("""
        MERGE (c:Cause {name: $cause})
        MERGE (d:Disease {name: $name})
        MERGE (d)-[:HAS_CAUSE]->(c)
        """, name=disease["name"], cause=disease["cause"])

    for precaution in disease.get("precautions", "").split(","):
        precaution = precaution.strip()
        if precaution:
            tx.run("""
            MERGE (p:Precaution {name: $precaution})
            MERGE (d:Disease {name: $name})
            MERGE (d)-[:HAS_PRECAUTION]->(p)
            """, name=disease["name"], precaution=precaution)

    for drug, desc in disease.get("drug_descriptions", {}).items():
        tx.run("""
        MERGE (dr:Drug {name: $drug})
        MERGE (d:Disease {name: $name})
        MERGE (d)-[:TREATED_BY]->(dr)
        """, name=disease["name"], drug=drug)
        tx.run("""
        MERGE (desc:Description {text: $desc})
        MERGE (dr:Drug {name: $drug})
        MERGE (dr)-[:HAS_DESCRIPTION]->(desc)
        """, drug=drug, desc=desc)

# ====== Load Triples for GAN Mode ======
def load_triples():
    with open("./RAG/data/synthetic_data.json") as f:
        data = json.load(f)

    triples = []
    for d in data:
        disease = d["name"]
        for s in d.get("symptoms", "").split(","):
            if s.strip(): triples.append((disease, "has_symptom", s.strip()))
        for p in d.get("precautions", "").split(","):
            if p.strip(): triples.append((disease, "has_precaution", p.strip()))
        if d.get("cause"):
            triples.append((disease, "has_cause", d["cause"].strip()))
        for drug, desc in d.get("drug_descriptions", {}).items():
            triples.append((disease, "treated_by", drug))
            triples.append((drug, "has_description", desc))
        if d.get("description"):
            triples.append((disease, "has_description", d["description"]))
    return triples, data

# ====== Build KG ======
def build_kg(train_gan=True):
    triples, original_data = load_triples()

    if not train_gan:
        with driver.session() as session:
            for d in original_data:
                session.execute_write(insert_triples, d)
                print(f"[INSERTED ✅] {d['name']}")
        return

    # ===== GAN Mode =====
    entities = list(set([h for h, _, _ in triples] + [t for _, _, t in triples]))
    relations = list(set([r for _, r, _ in triples]))
    entity2id = {e: i for i, e in enumerate(entities)}
    rel2id = {r: i for i, r in enumerate(relations)}
    triple_indices = [(entity2id[h], rel2id[r], entity2id[t]) for h, r, t in triples]

    FORCE_INSERT_PREDICATES = {"has_cause", "has_description", "has_precaution", "treated_by", "has_symptom"}
    THRESHOLD = -75.0

    embedding_dim = 50
    generator = DistMult(len(entities), len(relations), embedding_dim)
    discriminator = TransE(len(entities), len(relations), embedding_dim)
    g_optim = optim.Adam(generator.parameters(), lr=0.001)
    d_optim = optim.Adam(discriminator.parameters(), lr=0.001)

    # ===== Pretraining =====
    for model, opt in [(generator, g_optim), (discriminator, d_optim)]:
        for _ in range(50):
            for i in range(0, len(triple_indices), 16):
                batch = triple_indices[i:i + 16]
                h, r, t = zip(*batch)
                h, r, t = torch.tensor(h), torch.tensor(r), torch.tensor(t)
                neg_t = torch.randint(0, len(entities), h.size())
                loss = torch.mean(torch.clamp(1.0 - model(h, r, t) + model(h, r, neg_t), min=0))
                opt.zero_grad()
                loss.backward()
                opt.step()

    # ===== Adversarial training =====
    for _ in range(50):
        for i in range(0, len(triple_indices), 16):
            batch = triple_indices[i:i + 16]
            h, r, t = zip(*batch)
            h, r, t = torch.tensor(h), torch.tensor(r), torch.tensor(t)
            cand_t = torch.randint(0, len(entities), (len(h), 20))
            scores = generator(h.unsqueeze(1).repeat(1, 20), r.unsqueeze(1).repeat(1, 20), cand_t)
            probs = torch.softmax(scores, dim=1)
            neg_t = torch.multinomial(probs, 1).squeeze()

            # Discriminator update
            d_loss = torch.mean(torch.clamp(1.0 - discriminator(h, r, t) + discriminator(h, r, neg_t), min=0))
            d_optim.zero_grad()
            d_loss.backward()
            d_optim.step()

            # Generator update
            with torch.no_grad():
                rewards = -discriminator(h.unsqueeze(1).repeat(1, 20), r.unsqueeze(1).repeat(1, 20), cand_t)
                advantage = rewards - rewards.mean(dim=1, keepdim=True)
            log_probs = torch.log_softmax(scores, dim=1)
            g_loss = -torch.mean(advantage * log_probs)
            g_optim.zero_grad()
            g_loss.backward()
            g_optim.step()

    # ===== Scoring & filtering =====
    refined_triples = []
    scores_logged = []

    with torch.no_grad():
        for h, r, t in triple_indices:
            subj, pred, obj = entities[h], relations[r], entities[t]
            score = discriminator(torch.tensor([h]), torch.tensor([r]), torch.tensor([t])).item()
            scores_logged.append(score)
            if pred in FORCE_INSERT_PREDICATES or score > THRESHOLD:
                refined_triples.append((subj, pred, obj))
                print(f"[✅] {subj} -[{pred}]-> {obj} ({score:.2f})")
            else:
                print(f"[❌] {subj} -[{pred}]-> {obj} ({score:.2f})")

    # ===== Insert accepted triples to Neo4j =====
    def infer_type(entity):
        entity_lower = entity.lower()
        if any(symptom in entity_lower for symptom in ["fever", "fatigue", "cough", "ache", "sore", "headache"]):
            return "Symptom"
        elif "virus" in entity_lower or "bacteria" in entity_lower:
            return "Cause"
        elif "wash" in entity_lower or "mask" in entity_lower or "avoid" in entity_lower:
            return "Precaution"
        elif len(entity) > 150:
            return "Description"
        elif entity.istitle():
            return "Drug"
        return "Disease"

    with driver.session() as session:
        for h, r, t in refined_triples:
            h_type = infer_type(h)
            t_type = infer_type(t)
            if r == "has_description":
                session.run(
                    f"""
                    MERGE (a:{h_type} {{name: $h}})
                    MERGE (b:{t_type} {{text: $t}})
                    MERGE (a)-[:{r.upper()}]->(b)
                    """, {"h": h, "t": t}
                )
            else:
                session.run(
                    f"""
                    MERGE (a:{h_type} {{name: $h}})
                    MERGE (b:{t_type} {{name: $t}})
                    MERGE (a)-[:{r.upper()}]->(b)
                    """, {"h": h, "t": t}
                )

    print("\n🔹 Knowledge graph construction completed.")

# ===== Entry Point =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gan", action="store_true", help="Enable GAN filtering before inserting into Neo4j")
    args = parser.parse_args()

    if args.gan:
        print("[MODE: GAN FILTERING 🤖]")
    else:
        print("[MODE: DIRECT INSERTION 🚫 GAN]")

    build_kg(train_gan=args.gan)
