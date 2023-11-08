import speech_recognition as sr
import pyttsx3
from google.cloud import dialogflow_v2beta1 as dialogflow
import os
import json
from datetime import datetime, timedelta

# Initialisation
DIALOGFLOW_LANGUAGE_CODE = 'en'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "d41030virtualassistant-ftco-1e0f9e2b5bd7.json" # Google service account key
project_id = "d41030virtualassistant-ftco"  # Dialogflow project ID
session_id = "123456" # Random number
recogniser = sr.Recognizer()
engine = pyttsx3.init()


# write function (for when changes are made to data set)
# with open('books_dataset.json', 'w') as file:
#     json.dump(books_dataset, file, indent=4)

# Initialise json dataset 
with open('books_dataset.json', 'r') as file:
    books_dataset = json.load(file)


def detect_intent_texts(project_id, session_id, text, language_code):
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)
    
    intent_name = response.query_result.intent.display_name
    #print(f"Intent name: {intent_name}")
    fulfillment_text = response.query_result.fulfillment_text # Dialogflow output
    
    # Consider including intent for looking up commands e.g. "what can you do"
    if intent_name == "Search Intent":
        print("search function here")
    elif intent_name == "View Reserved Intent":
        print("view reserved function here")
    elif intent_name == "FAQ Intent":
        print("faq function here")
    else:
        return fulfillment_text # Default fallback intent output   

    return fulfillment_text # May need to move this to the if/elif block





# Function to speak a response
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Function to listen for audio and convert it to text
def listen():
    with sr.Microphone() as source:
        print(f"Listening...") # Could change this to show potential commands or something
        audio = recogniser.listen(source)
        
        try:
            return recogniser.recognize_google(audio).lower()
        except sr.UnknownValueError:
            return "I couldn't understand what you said, please try again."
        except sr.RequestError:
            return "I'm having trouble connecting to the speech service."


def main():
    # Consider printing/speaking out an introduction line, or a login line
    print("Welcome to Library Virtual Assistant")
    
    while True:
        # Listen for commands
        command = listen()
        print(f"You said: {command}")          
        if 'stop listening' in command:
            print("Goodbye!") # Could change to assistant speaking, or just add it
            break
        else: 
            response_text = detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
            speak(response_text)


 

if __name__ == "__main__":
    main()
