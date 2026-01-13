"""
FastAPI Pronunciation Assessment API

Run with: uvicorn api:app --reload
Swagger UI available at: http://localhost:8000/docs
"""

import os
import json
import tempfile
import subprocess
import shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Pronunciation Assessment API",
    description="Azure Speech Services pronunciation assessment with IPA phoneme support",
    version="1.0.0",
)

# Enable CORS for frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Response Models (for Swagger documentation)
# ─────────────────────────────────────────────────────────────────────────────

class PhonemeResult(BaseModel):
    phoneme: str
    accuracy_score: Optional[float] = None


class WordResult(BaseModel):
    word: str
    accuracy_score: Optional[float] = None
    error_type: Optional[str] = None
    phonemes: list[PhonemeResult] = []


class PronunciationResponse(BaseModel):
    recognized_text: str
    accuracy_score: float
    fluency_score: float
    completeness_score: Optional[float] = None
    prosody_score: Optional[float] = None
    pronunciation_score: Optional[float] = None
    words: list[WordResult] = []
    assessment_type: str


class HealthResponse(BaseModel):
    status: str
    ffmpeg_available: bool


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is installed on the system."""
    return shutil.which("ffmpeg") is not None


def convert_to_azure_wav(input_path: str, output_path: str) -> bool:
    """
    Convert audio file to Azure-compatible WAV format:
    - 16kHz sample rate
    - Mono channel
    - 16-bit PCM
    """
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000",       # 16kHz sample rate
                "-ac", "1",           # Mono
                "-sample_fmt", "s16", # 16-bit
                "-f", "wav",
                output_path
            ],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_file_extension(filename: Optional[str]) -> str:
    """Extract file extension from filename."""
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ".wav"


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Basic health check endpoint."""
    return {"status": "ok", "message": "Pronunciation Assessment API is running"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if the API is running and ffmpeg is available."""
    return HealthResponse(
        status="healthy",
        ffmpeg_available=is_ffmpeg_available()
    )


@app.post("/assess", response_model=PronunciationResponse)
async def assess_pronunciation(
    audio_file: UploadFile = File(..., description="Audio file (WAV, WebM, MP3, M4A, etc.)"),
    reference_text: str = Query(
        default="",
        description="Reference text for scripted assessment. Leave empty for unscripted assessment."
    )
):
    """
    Assess pronunciation of uploaded audio using Azure Speech Services.
    
    **Supported audio formats:** WAV, WebM, MP3, M4A, OGG, FLAC (requires ffmpeg for non-WAV)
    
    **Assessment types:**
    - **Unscripted:** Leave `reference_text` empty. Assesses whatever is spoken.
    - **Scripted:** Provide `reference_text`. Compares speech against expected text and detects miscues.
    
    **Returns:** Detailed pronunciation scores including accuracy, fluency, prosody,
    plus word-level and phoneme-level (IPA) breakdowns.
    """
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    service_region = os.getenv("AZURE_SERVICE_REGION", "eastus")
    
    if not speech_key:
        raise HTTPException(
            status_code=500,
            detail="AZURE_SPEECH_KEY not configured. Set it in your .env file."
        )
    
    # Save uploaded file temporarily
    file_ext = get_file_extension(audio_file.filename)
    
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp_in:
        content = await audio_file.read()
        tmp_in.write(content)
        tmp_in_path = tmp_in.name
    
    # Determine if we need to convert the audio
    wav_path = tmp_in_path
    needs_conversion = file_ext.lower() not in [".wav"]
    converted_path = None
    
    try:
        if needs_conversion:
            if not is_ffmpeg_available():
                raise HTTPException(
                    status_code=400,
                    detail=f"Audio format '{file_ext}' requires ffmpeg for conversion, but ffmpeg is not installed. "
                           f"Please upload a WAV file or install ffmpeg on the server."
                )
            
            converted_path = tmp_in_path.rsplit(".", 1)[0] + "_converted.wav"
            if not convert_to_azure_wav(tmp_in_path, converted_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to convert audio file. Please ensure the file is a valid audio format."
                )
            wav_path = converted_path
        
        # Azure Speech config
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        
        is_scripted = bool(reference_text and reference_text.strip())
        
        # Configure pronunciation assessment with IPA phonemes
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            json_string=json.dumps({
                "referenceText": reference_text,
                "gradingSystem": "HundredMark",
                "granularity": "Phoneme",
                "phonemeAlphabet": "IPA",
                "enableMiscue": is_scripted,
                "enableProsodyAssessment": True
            })
        )
        
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        pronunciation_config.apply_to(speech_recognizer)
        
        # Perform recognition
        result = speech_recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            pron_result = speechsdk.PronunciationAssessmentResult(result)
            
            # Build word-level details with phonemes
            words = []
            if hasattr(pron_result, 'words') and pron_result.words:
                for word in pron_result.words:
                    phonemes = []
                    if hasattr(word, 'phonemes') and word.phonemes:
                        phonemes = [
                            PhonemeResult(
                                phoneme=p.phoneme,
                                accuracy_score=getattr(p, 'accuracy_score', None)
                            ) for p in word.phonemes
                        ]
                    words.append(WordResult(
                        word=word.word,
                        accuracy_score=getattr(word, 'accuracy_score', None),
                        error_type=getattr(word, 'error_type', None),
                        phonemes=phonemes
                    ))
            
            # If no words from SDK, try parsing JSON result
            if not words:
                try:
                    json_result = result.json
                    if json_result:
                        result_data = json.loads(json_result)
                        if 'NBest' in result_data and len(result_data['NBest']) > 0:
                            nbest = result_data['NBest'][0]
                            if 'Words' in nbest:
                                for word_data in nbest['Words']:
                                    phonemes = []
                                    if 'Phonemes' in word_data:
                                        for p in word_data['Phonemes']:
                                            pa = p.get('PronunciationAssessment', {})
                                            phonemes.append(PhonemeResult(
                                                phoneme=p.get('Phoneme', ''),
                                                accuracy_score=pa.get('AccuracyScore')
                                            ))
                                    
                                    word_pa = word_data.get('PronunciationAssessment', {})
                                    words.append(WordResult(
                                        word=word_data.get('Word', ''),
                                        accuracy_score=word_pa.get('AccuracyScore'),
                                        error_type=word_pa.get('ErrorType'),
                                        phonemes=phonemes
                                    ))
                except Exception:
                    pass  # Use empty words list if JSON parsing fails
            
            return PronunciationResponse(
                recognized_text=result.text,
                accuracy_score=pron_result.accuracy_score,
                fluency_score=pron_result.fluency_score,
                completeness_score=getattr(pron_result, 'completeness_score', None),
                prosody_score=getattr(pron_result, 'prosody_score', None),
                pronunciation_score=getattr(pron_result, 'pronunciation_score', None),
                words=words,
                assessment_type="SCRIPTED" if is_scripted else "UNSCRIPTED"
            )
        
        elif result.reason == speechsdk.ResultReason.NoMatch:
            raise HTTPException(
                status_code=400,
                detail="No speech could be recognized in the audio. Please ensure the audio contains clear speech."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Speech recognition error: {result.reason}"
            )
    
    finally:
        # Clean up temporary files
        if os.path.exists(tmp_in_path):
            os.unlink(tmp_in_path)
        if converted_path and os.path.exists(converted_path):
            os.unlink(converted_path)

