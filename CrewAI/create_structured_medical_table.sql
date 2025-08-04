-- Create table for storing structured medical data extracted from LLM responses
CREATE TABLE IF NOT EXISTS public."StructuredMedicalData" (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    health_query_response_id INTEGER REFERENCES public."HealthQueryResponse"(id),
    symptoms TEXT, -- JSON string of symptoms array
    diagnoses TEXT, -- JSON string of diagnoses array
    treatments TEXT, -- JSON string of treatments array
    precautions TEXT, -- JSON string of precautions array
    severity VARCHAR(100),
    duration VARCHAR(100),
    parsed_content JSONB, -- Full parsed JSON content from LLM
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_structured_medical_session_id ON public."StructuredMedicalData"(session_id);
CREATE INDEX IF NOT EXISTS idx_structured_medical_health_query_id ON public."StructuredMedicalData"(health_query_response_id);
CREATE INDEX IF NOT EXISTS idx_structured_medical_created_at ON public."StructuredMedicalData"(created_at);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_structured_medical_updated_at 
    BEFORE UPDATE ON public."StructuredMedicalData" 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE public."StructuredMedicalData" IS 'Stores structured medical data extracted from LLM responses';
COMMENT ON COLUMN public."StructuredMedicalData".symptoms IS 'JSON array of symptoms extracted from LLM response';
COMMENT ON COLUMN public."StructuredMedicalData".diagnoses IS 'JSON array of possible diagnoses';
COMMENT ON COLUMN public."StructuredMedicalData".treatments IS 'JSON array of suggested treatments';
COMMENT ON COLUMN public."StructuredMedicalData".precautions IS 'JSON array of precautions and advice';
COMMENT ON COLUMN public."StructuredMedicalData".parsed_content IS 'Complete parsed JSON content from LLM response'; 