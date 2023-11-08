import speech_recognition as sr
import pyttsx3
from google.cloud import dialogflow_v2beta1 as dialogflow
import os

DIALOGFLOW_LANGUAGE_CODE = 'en'


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "d41030virtualassistant-ftco-1e0f9e2b5bd7.json" # Google service account key

def detect_intent_texts(project_id, session_id, text, language_code):
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)

    return response.query_result.fulfillment_text

project_id = "d41030virtualassistant-ftco"  # Dialogflow project ID
session_id = "123456" # Random number


# Initialisation of speech recognition, tts engine, and spaCy model and matcher
recogniser = sr.Recognizer()
engine = pyttsx3.init()

# Function to speak a response
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Function to listen for audio and convert it to text
def listen():
    with sr.Microphone() as source:
        print("Listening...") #could change this to show potential commands or something
        audio = recogniser.listen(source)
        
        try:
            return recogniser.recognize_google(audio).lower()
        except sr.UnknownValueError:
            return "I couldn't understand what you said, please try again."
        except sr.RequestError:
            return "I'm having trouble connecting to the speech service."


def main():
    while True:
        # Listen for commands
        command = listen()
               
        if 'stop listening' in command:
            print("Goodbye!") #could change to assistant speaking
            break
        
        print(f"You said: {command}")    
        response_text = detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
        speak(response_text)
        # Check if the user said 'search for', or find intents

 

if __name__ == "__main__":
    main()
