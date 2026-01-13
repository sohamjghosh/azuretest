# Azure Pronunciation Assessment API

A FastAPI wrapper for Azure Speech Services pronunciation assessment with automatic Swagger/OpenAPI documentation.



1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your `.env` file with Azure credentials:
```
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SERVICE_REGION=eastus
```

## Running the API

Start the FastAPI server:
```bash
python app.py
```

Or using uvicorn directly:
```bash
uvicorn app:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### POST `/assess-pronunciation`

Assess pronunciation from an uploaded audio file.

**Parameters:**
- `audio_file` (file): WAV audio file (16kHz, 16-bit, mono recommended)
- `reference_text` (optional, string): Reference text for scripted assessment. Leave empty for unscripted assessment.
- `enable_prosody` (optional, boolean): Enable prosody assessment (default: true)
- `grading_system` (optional, string): Grading system - "HundredMark" or "FivePoint" (default: "HundredMark")
- `granularity` (optional, string): Granularity level - "Phoneme", "Word", or "FullText" (default: "Phoneme")

**Response:**
```json
{
  "assessment_type": "SCRIPTED" | "UNSCRIPTED",
  "accuracy_score": 85.5,
  "fluency_score": 90.2,
  "completeness_score": 88.0,
  "prosody_score": 87.5,
  "pronunciation_score": 87.8,
  "recognized_text": "The recognized text from the audio",
  "reference_text": "The reference text (if scripted)",
  "words": [
    {
      "word": "example",
      "accuracy_score": 90.0,
      "error_type": "None",
      "phonemes": [
        {
          "phoneme": "ɪɡ",
          "accuracy_score": 95.0
        }
      ]
    }
  ],
  "miscue_info": ["'word': Omission"]
}
```

### GET `/health`

Check API health and Azure configuration status.

### GET `/`

Basic health check endpoint.

## Using Swagger UI

1. Start the server
2. Navigate to http://localhost:8000/docs
3. Click on `/assess-pronunciation` endpoint
4. Click "Try it out"
5. Upload an audio file and configure parameters
6. Click "Execute" to see the results

## Example Usage with curl

```bash
curl -X POST "http://localhost:8000/assess-pronunciation" \
  -F "audio_file=@recording.wav" \
  -F "reference_text=Hello world" \
  -F "enable_prosody=true"
```

## Example Usage with Python

```python
import requests

url = "http://localhost:8000/assess-pronunciation"
files = {"audio_file": open("recording.wav", "rb")}
data = {
    "reference_text": "Hello world",
    "enable_prosody": "true"
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

## Notes

- Audio files should be in WAV format with 16kHz sample rate, 16-bit depth, and mono channel for best results
- For scripted assessment, provide a `reference_text` parameter
- For unscripted assessment, leave `reference_text` empty
- The API automatically handles temporary file cleanup


# Unscripted assessment
curl -X POST "http://localhost:8000/assess" \
  -F "audio_file=@recording.wav"

# Scripted assessment
curl -X POST "http://localhost:8000/assess?reference_text=hello%20world" \
  -F "audio_file=@recording.wav"

## Deploying to Railway

This project is configured for easy deployment to Railway.

### Prerequisites
- A Railway account (sign up at [railway.app](https://railway.app))
- An Azure Speech Services key and region

### Deployment Steps

1. **Install Railway CLI** (optional, but recommended):
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**:
   ```bash
   railway login
   ```

3. **Initialize Railway project** (if not using GitHub integration):
   ```bash
   railway init
   ```

4. **Set Environment Variables**:
   In the Railway dashboard or via CLI:
   ```bash
   railway variables set AZURE_SPEECH_KEY=your_azure_speech_key_here
   railway variables set AZURE_SERVICE_REGION=eastus
   ```
   
   If you encounter Python installation issues, you can also set:
   ```bash
   railway variables set RAILPACK_PYTHON_VERSION=3.11
   ```

5. **Deploy**:
   ```bash
   railway up
   ```
   
   Or connect your GitHub repository to Railway for automatic deployments.

### Railway Configuration Files

The following files are included for Railway deployment:
- `Procfile` - Defines the web process
- `railway.json` - Railway-specific configuration
- `nixpacks.toml` - Build configuration (installs Python and ffmpeg)
- `app.py` - Entry point for Railway to auto-detect FastAPI

### Important Notes for Railway

- The app automatically uses the `PORT` environment variable provided by Railway
- `ffmpeg` is installed via Nixpacks configuration for audio format conversion
- Make sure to set `AZURE_SPEECH_KEY` and `AZURE_SERVICE_REGION` as environment variables in Railway
- If you encounter Python version issues, you can set `RAILPACK_PYTHON_VERSION=3.11` as an environment variable (Railway will auto-detect Python 3.11+ from your requirements.txt otherwise)
- The API will be available at the Railway-provided domain (e.g., `https://your-app.railway.app`)

### Testing the Deployment

Once deployed, you can test the API:
```bash
# Health check
curl https://your-app.railway.app/health

# Assess pronunciation
curl -X POST "https://your-app.railway.app/assess" \
  -F "audio_file=@recording.wav" \
  -F "reference_text=Hello world"
```
