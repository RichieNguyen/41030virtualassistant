import speech_recognition as sr
import pyttsx3
from google.cloud import dialogflow_v2beta1 as dialogflow
import os
import json
from datetime import datetime, timedelta
from word2number import w2n
import isodate

# Initialisation
DIALOGFLOW_LANGUAGE_CODE = 'en'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "d41030virtualassistant-ftco-1e0f9e2b5bd7.json" # Google service account key
project_id = "d41030virtualassistant-ftco"  # Dialogflow project ID
session_id = "12345" # Random number, change for new sessions when debugging for follow-up intents
recogniser = sr.Recognizer()
engine = pyttsx3.init()
#userid = None
userid ='123'
current_reservation = {}

# Initialise json dataset 
with open('books_dataset.json', 'r') as file:
    books_dataset = json.load(file)


def detect_intent_texts(project_id, session_id, text, language_code):
    global current_reservation
    global userid
    
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)
    
    intent_name = response.query_result.intent.display_name
    # Debug
    #print(f"Intent name: {intent_name}")
    fulfillment_text = response.query_result.fulfillment_text # Dialogflow output
    
    
    # Consider including intent for looking up commands e.g. "what can you do"
    if intent_name == "Search Intent":
        speak(fulfillment_text)
        parameters = dict(response.query_result.parameters)
        title = parameters.get('title', '')        
        author = parameters.get('author', '')
        genre = parameters.get('genre', '')

        # Debug


        #print("Title:", title)
        #print("Author:", author)
        #print("Genre:", genre)
        
        if not (title or author or genre):
            speak("Sorry, I didn't understand your query, please include the title, author, or genre of the book you are trying to search.")
        else:
            results = search_books(title, author, genre)
            print_search_results(results)
            if results:
                check_search_availability(results)
    elif intent_name == "Reserve Intent":
        parameters = dict(response.query_result.parameters)
        title = parameters.get('title', '')        
        id = parameters.get('id', '')
        
        # Convert id value into an integer for search function
        if id is not None and isinstance(id, (float, int)):
            id = int(id)
        
        search_results = search_books_by_title_or_id(title, id)
        num_results = len(search_results)

        if num_results == 1: # Reserve only if one book found, ask for duration of reservation
            # need to include check on whether the book is already reserved or not
            print_search_results(search_results)
            current_reservation['title'] = search_results[0]['title']
            current_reservation['ID'] = search_results[0]['ID']    
            if check_reserved(search_results[0]):
                remove_context(project_id, session_id, 'ReserveIntent-followup')
                current_reservation = {}       
     
        elif num_results > 1:
            remove_context(project_id, session_id, 'ReserveIntent-followup')
            current_reservation = {}
            print_search_results(search_results)
            speak("Multiple books found. Please be more specific.")
        else:
            remove_context(project_id, session_id, 'ReserveIntent-followup')
            current_reservation = {}
            speak("There is no book with this ID or name, please try again")
    #optionally, add cancel intent (cancelling current action/followup intents)
    elif intent_name == "Duration Intent":
        parameters = dict(response.query_result.parameters)        
        title = current_reservation.get('title')
        id = current_reservation.get('ID')
        duration = parameters.get('duration', '')
        
        # Convert id value into an integer for search function
        if id is not None and isinstance(id, (float, int)):
            id = int(id)
        
        duration_days = convert_iso_duration_to_days(duration)
        print(duration_days)

        for book in books_dataset:
            if book['ID'] == id:
                start_date = datetime.now()
                end_date = start_date + timedelta(days=duration_days) 
                end_date_str = end_date.strftime("%Y-%m-%d")
                
                book['reserved'] = True
                book['reservation'] = end_date_str
                book['reservedBy'] = userid
                # Update .json file with book and reservation details
                with open('books_dataset.json', 'w') as f:
                    json.dump(books_dataset, f, indent=4)
                current_reservation = {}
                break
    elif intent_name == "View Reserved Intent":
        #create the intent in dialogflow
        #check if any books are reserved under user id
        #if yes, show all books reserved
        #if no, say no books reserved
        print("view reserved function here")
    elif intent_name == "Return Intent":
        #check if any parameters given (if no, prompt for parameters)
        #check if book is reserved by current userid
        #if no, say so and end intent
        #if yes, ask for confirmation? or just process return
        print("return book intent here")
    elif intent_name == "FAQ Intent":
        #look at faq prebuilt agent/intent in dialogflow
        #if can't then look at other methods of faq (qnamaker, etc)
        print("faq function here")
    else:
        return  

    return 

# Function to remove follow-up contexts, for when a function is called but cannot be executed (e.g. attempting to reserve a book that is already reserved)
def remove_context(project_id, session_id, context_name):
    client = dialogflow.ContextsClient()
    context_path = client.context_path(project_id, session_id, context_name)
    client.delete_context(name=context_path)

def get_duration_string_from_mapcomposite(duration_map):
    amount = duration_map.get('amount', 0)
    unit = duration_map.get('unit', '').lower()
    
    amount_str = str(amount)

    if unit in ['h', 'hour', 'hours']:
        return f"PT{amount_str}H"
    elif unit in ['m', 'minute', 'minutes']:
        return f"PT{amount_str}M"
    elif unit in ['s', 'second', 'seconds']:
        return f"PT{amount_str}S"
    elif unit in ['d', 'day', 'days']:
        return f"P{amount_str}D"
    elif unit in ['wk', 'week', 'weeks']:
        return f"P{amount_str}W"
    elif unit in ['mo', 'month', 'months']:
        return f"P{amount_str}M" 
    elif unit in ['y', 'year', 'years']:
        return f"P{amount_str}Y"  

    return ""

def convert_iso_duration_to_days(duration_map):
    try:
        duration_str = get_duration_string_from_mapcomposite(duration_map)
        parsed_duration = isodate.parse_duration(duration_str)

        total_days = parsed_duration.days
        
        # Check if the duration is below the minimum (1 day)
        if total_days == 0 and parsed_duration.seconds > 0:
            return 0

        # Check if the duration is above the maximum (10 days)
        if total_days > 10:
            return 11

        return total_days
    except Exception as e:
        print(f"Error parsing duration: {e}")
        return None

def search_books(title=None, author=None, genre=None):
    results = []
    for book in books_dataset:
        if title and title.lower() not in book['title'].lower():
            continue
        if author and author.lower() not in book['author'].lower():
            continue
        if genre and genre.lower() not in book['genre'].lower():
            continue
        results.append(book)
    return results

def search_books_by_title_or_id(title=None, id=None):
    results = []
    for book in books_dataset:
        if title and title.lower() in book['title'].lower():
            results.append(book)
        elif id and str(book['ID']) == str(id):
            results.append(book)
    return results
        
def check_reserved(book):
    if book['reserved']:
        speak(f"The book '{book['title']}' is already reserved until {book['reservation']}.")
        return True
    speak(f"The book '{book['title']}' is available for reservation, how long would you like to reserve it for (1-10 days).")
    return False
   

def print_search_results(results):
    if not results:
        speak("No books found under those criteria. Please enter a new query")
        return
    for book in results:
        if book['reserved'] is False:
            print(f"""
            ID: {book["ID"]}
            Title: {book['title']}
            Author: {book['author']}
            Genre: {book['genre']}
            Description: {book['description']}
            Reserved: No
            """)
        elif book['reserved'] is True:
            print(f"""
            ID: {book["ID"]}
            Title: {book['title']}
            Author: {book['author']}
            Genre: {book['genre']}
            Description: {book['description']}
            Reserved: Yes
            Reservation: {book['reservation']}
            """)

def check_search_availability(results):
    available_books = [book for book in results if not book['reserved']]
    
    if not available_books:
        speak("None of the listed books are available for reservation, please enter a new query")
        return
    speak("There are books listed that are available for reservation, let me know the title or ID of the book you would like to reserve. Otherwise please enter a new query.")



# Function to speak a response
def speak(text):
    print(text)
    engine.say(text)
    engine.runAndWait()
 
# Function to convert number words into numerical values in a string e.g. one -> 1 
def convert_numbers(text):
    words = text.split()
    converted_text = []
    for word in words:
        try:
            number = w2n.word_to_num(word)
            converted_text.append(str(number))
        except ValueError:
            converted_text.append(word)
    return ' '.join(converted_text)   

# Function to listen for audio and convert it to text
def listen():
    with sr.Microphone() as source:
        print(f"Listening...") # Could change this to show potential commands or something
        audio = recogniser.listen(source)
        
        try:
            text = convert_numbers(recogniser.recognize_google(audio).lower())
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            return "I couldn't understand what you said, please try again."
        except sr.RequestError:
            return "I'm having trouble connecting to the speech service."


def main():
    global userid
    #include a function to check for reservaation dates of json, update when a reservation expires - convert the string value back into a datetime format and verify through current date
    
    
    # Save time debugging by commenting out this beginning section and setting a global userid variable
    #speak("Welcome to Library Virtual Assistant")
    #speak(f"Please login with your user id")
    #userid = listen()
    #print(f"Logged into {userid}")
    #speak(f"Please speak your query, you can search, reserve, view your reservations, or ask a question if its in the FAQ.")
    #speak(f"Say 'stop listening' if you no longer have queries.")
    
    while True:
        # Listen for commands
        #command = listen()
        
        # Debug
        command = "reserve 1"
        
        
        if 'stop listening' in command:
            print("Goodbye!") # Could change to assistant speaking, or just add it
            break
        else: 
            detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
            command = "reserve for 10080 minutes"
            detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
            
            # Debug with manual command line
            break
        
 

 

if __name__ == "__main__":
    main()
