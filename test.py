import azure.cognitiveservices.speech as speechsdk
import os
import json
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf


def record_audio(filename="recording.wav", duration=10, sample_rate=16000):
    """
    Record audio with Azure-compatible format
    - 16kHz sample rate
    - 16-bit depth
    - Mono channel
    """
    print(f"Recording for {duration} seconds...")
    print("Speak now...")
    
    # Record audio
    recording = sd.rec(
        int(duration * sample_rate),  # Number of samples
        samplerate=sample_rate,
        channels=1,  # Mono
        dtype='int16'  # 16-bit
    )
    
    sd.wait()  # Wait until recording is finished
    
    # Save as WAV file
    sf.write(filename, recording, sample_rate, subtype='PCM_16')
    print(f"Recording saved to {filename}")
    
    return filename


def assess_pronunciation(audio_file, speech_key, service_region, reference_text=""): #change for scripted assesment
    """
    Send audio file to Azure for pronunciation assessment
    
    Args:
        audio_file: Path to the audio file
        speech_key: Azure Speech service key
        service_region: Azure service region
        reference_text: Reference text for scripted assessment. 
                       If empty (""), performs unscripted assessment.
    """
    # Create speech config
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key, 
        region=service_region
    )
    
    # Read from WAV file
    audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
    
    # Determine if scripted or unscripted
    is_scripted = bool(reference_text and reference_text.strip())
    
    # Set up pronunciation assessment
    # Using JSON to configure IPA phoneme alphabet
    pronunciation_config_json = json.dumps({
        "referenceText": reference_text,  # Empty for unscripted, text for scripted
        "gradingSystem": "HundredMark",
        "granularity": "Phoneme",
        "phonemeAlphabet": "IPA",  # Use IPA format instead of SAPI
        "enableMiscue": is_scripted,  # Enable miscue detection for scripted assessment
        "enableProsodyAssessment": True
    })
    
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        json_string=pronunciation_config_json
    )
    
    # Create speech recognizer
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    
    # Apply pronunciation assessment
    pronunciation_config.apply_to(speech_recognizer)
    
    # Recognize and get results
    print("Sending audio to Azure for assessment...")
    result = speech_recognizer.recognize_once()
    
    # Extract pronunciation scores
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        
        # Also get JSON result for detailed phoneme access
        json_result = result.json
        
        assessment_type = "SCRIPTED" if is_scripted else "UNSCRIPTED"
        print("\n" + "="*60)
        print(f"=== PRONUNCIATION ASSESSMENT RESULTS ({assessment_type}) ===")
        print("="*60)
        
        if is_scripted:
            print(f"\n--- Reference Text ---")
            print(f"{reference_text}")
        
        # Core metrics available for unscripted audio
        print("\n--- Core Scores (0-100) ---")
        print(f"Accuracy Score:    {pronunciation_result.accuracy_score:.2f}%")
        print(f"Fluency Score:     {pronunciation_result.fluency_score:.2f}%")
        
        # Completeness may not be applicable for unscripted/speaking scenario
        if hasattr(pronunciation_result, 'completeness_score') and pronunciation_result.completeness_score is not None:
            print(f"Completeness Score: {pronunciation_result.completeness_score:.2f}%")
        
        # Prosody score (if enabled)
        if hasattr(pronunciation_result, 'prosody_score') and pronunciation_result.prosody_score is not None:
            print(f"Prosody Score:      {pronunciation_result.prosody_score:.2f}%")
        
        # Pronunciation score (weighted overall score)
        if hasattr(pronunciation_result, 'pronunciation_score') and pronunciation_result.pronunciation_score is not None:
            print(f"Pronunciation Score: {pronunciation_result.pronunciation_score:.2f}%")
        
        print(f"\n--- Recognized Text ---")
        print(f"{result.text}")
        
        # Word-level details (if available)
        phoneme_count = 0
        miscue_info = []
        if hasattr(pronunciation_result, 'words') and pronunciation_result.words:
            print(f"\n--- Word-Level Details ---")
            for word in pronunciation_result.words:
                word_info = f"Word: '{word.word}'"
                if hasattr(word, 'accuracy_score'):
                    word_info += f" | Accuracy: {word.accuracy_score:.2f}%"
                if hasattr(word, 'error_type'):
                    error_type = word.error_type
                    word_info += f" | Error Type: {error_type}"
                    if error_type:
                        miscue_info.append(f"'{word.word}': {error_type}")
                print(word_info)
                
                # Phoneme-level details are nested within words
                if hasattr(word, 'phonemes') and word.phonemes:
                    phoneme_count += len(word.phonemes)
        
        # Display miscue information (omissions and insertions) for scripted assessment
        if is_scripted and miscue_info:
            print(f"\n--- Miscue Information (Omissions/Insertions) ---")
            for miscue in miscue_info:
                print(f"  {miscue}")
        elif is_scripted:
            # Try to get miscue info from JSON
            try:
                if json_result:
                    result_data = json.loads(json_result)
                    if 'NBest' in result_data and len(result_data['NBest']) > 0:
                        nbest = result_data['NBest'][0]
                        if 'Words' in nbest:
                            miscues_found = False
                            print(f"\n--- Miscue Information from JSON ---")
                            for word in nbest['Words']:
                                if 'PronunciationAssessment' in word:
                                    pa = word['PronunciationAssessment']
                                    error_type = pa.get('ErrorType', '')
                                    if error_type:
                                        miscues_found = True
                                        word_text = word.get('Word', 'N/A')
                                        print(f"  '{word_text}': {error_type}")
                            if not miscues_found:
                                print("  No miscues detected (all words match reference text)")
            except Exception as e:
                print(f"\n--- Note: Could not extract miscue info from JSON: {e} ---")
        
        # Display phoneme-level details (nested within words) in IPA format
        if phoneme_count > 0:
            print(f"\n--- Phoneme-Level Details in IPA Format (Total: {phoneme_count}) ---")
            phoneme_displayed = 0
            for word in pronunciation_result.words:
                if hasattr(word, 'phonemes') and word.phonemes:
                    print(f"\n  IPA Phonemes in '{word.word}':")
                    for phoneme in word.phonemes:
                        if phoneme_displayed < 20:  # Show first 20 phonemes
                            phoneme_info = f"    /{phoneme.phoneme}/"  # IPA notation uses / /
                            if hasattr(phoneme, 'accuracy_score'):
                                phoneme_info += f" | Accuracy: {phoneme.accuracy_score:.2f}%"
                            print(phoneme_info)
                            phoneme_displayed += 1
                        else:
                            break
                    if phoneme_displayed >= 20:
                        break
            if phoneme_count > 20:
                print(f"\n  ... and {phoneme_count - 20} more phonemes")
        else:
            # Try to get phonemes from JSON result
            try:
                if json_result:
                    result_data = json.loads(json_result)
                    # Navigate through JSON structure to find phonemes
                    if 'NBest' in result_data and len(result_data['NBest']) > 0:
                        nbest = result_data['NBest'][0]
                        if 'Words' in nbest:
                            all_phonemes = []
                            for word in nbest['Words']:
                                if 'Phonemes' in word:
                                    all_phonemes.extend(word['Phonemes'])
                            
                            if all_phonemes:
                                print(f"\n--- Phoneme-Level Details in IPA Format from JSON (Total: {len(all_phonemes)}) ---")
                                for i, phoneme in enumerate(all_phonemes[:20]):
                                    phoneme_symbol = phoneme.get('Phoneme', 'N/A')
                                    phoneme_info = f"  /{phoneme_symbol}/"  # IPA notation uses / /
                                    if 'PronunciationAssessment' in phoneme:
                                        pa = phoneme['PronunciationAssessment']
                                        if 'AccuracyScore' in pa:
                                            phoneme_info += f" | Accuracy: {pa['AccuracyScore']:.2f}%"
                                    print(phoneme_info)
                                if len(all_phonemes) > 20:
                                    print(f"  ... and {len(all_phonemes) - 20} more phonemes")
            except Exception as e:
                print(f"\n--- Note: Could not extract phonemes from JSON: {e} ---")
                # Debug: Check what attributes are available
                print(f"\n--- Debug: Available attributes ---")
                print(f"PronunciationResult attributes: {[attr for attr in dir(pronunciation_result) if not attr.startswith('_')]}")
                if hasattr(pronunciation_result, 'words') and pronunciation_result.words:
                    print(f"First word attributes: {[attr for attr in dir(pronunciation_result.words[0]) if not attr.startswith('_')]}")
        
        print("\n" + "="*60)
        
        return pronunciation_result
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized")
        return None
    else:
        print(f"Error: {result.reason}")
        return None


def main():
    
    load_dotenv()
    
    
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    service_region = os.getenv("AZURE_SERVICE_REGION", "eastus")
    
    if not speech_key:
        print("Error: AZURE_SPEECH_KEY not found in .env file")
        return

    print("Recording new audio...")
    audio_file = record_audio("recording.wav")  # Uses default duration=10
    
    
    # Assess pronunciation
    # For SCRIPTED assessment (uses default reference text from function definition):
    assess_pronunciation(audio_file, speech_key, service_region)
    


if __name__ == "__main__":
    main()
