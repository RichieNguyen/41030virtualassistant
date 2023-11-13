import speech_recognition as sr
import pyttsx3
from google.cloud import dialogflow_v2beta1 as dialogflow
import os
import json
from datetime import datetime, timedelta
from word2number import w2n
import isodate
import spacy
import sys

# Initialisation
DIALOGFLOW_LANGUAGE_CODE = 'en'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "d41030virtualassistant-ftco-1e0f9e2b5bd7.json" # Google service account key
project_id = "d41030virtualassistant-ftco"  # Dialogflow project ID
session_id = "12346" # Random number, change for new sessions when debugging for follow-up intents
recogniser = sr.Recognizer()
engine = pyttsx3.init()
userid = None
current_reservation = {}
current_return ={}
nlp = spacy.load("en_core_web_sm")

# Initialise json datasets
with open('books_dataset.json', 'r') as file:
    books_dataset = json.load(file)    
with open('uts_faq.json', 'r') as file:
    faq = json.load(file)

def detect_intent_texts(project_id, session_id, text, language_code):
    global current_reservation
    global current_return
    global userid
    
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)

    text_input = dialogflow.TextInput(text=text, language_code=language_code)
    query_input = dialogflow.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)
    
    intent_name = response.query_result.intent.display_name
    # Debug
    # print(f"Intent name: {intent_name}")
    fulfillment_text = response.query_result.fulfillment_text # Dialogflow output
    
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
            else:
                speak("No books found under those crtieria.")    
    elif intent_name == "Reserve Intent":
        parameters = dict(response.query_result.parameters)
        title = parameters.get('title', '')        
        id = parameters.get('id', '')
        
        if id is not None and isinstance(id, (float, int)):
            id = int(id)
        
        search_results = search_books_by_title_or_id(title, id)
        num_results = len(search_results)
        print_search_results(search_results)

        if num_results == 1: # Reserve only if one book found, check reservation status, then ask for duration of reservation
            if check_reserved(search_results[0]):
                speak(f"The book '{search_results[0]['title']}' is already reserved until {search_results[0]['reservation']}.")
                remove_context(project_id, session_id, 'ReserveIntent-followup')
                current_reservation = {}
            else:
                current_reservation['title'] = search_results[0]['title']
                current_reservation['ID'] = search_results[0]['ID']
                speak(f"The book '{search_results[0]['title']}' is available for reservation, how long would you like to reserve it for (1-10 days).")                            
        elif num_results > 1:
            remove_context(project_id, session_id, 'ReserveIntent-followup')
            current_reservation = {}

            speak("Multiple books found. Please be more specific.")
        else:
            remove_context(project_id, session_id, 'ReserveIntent-followup')
            current_reservation = {}
            speak("There is no book with this ID or name, please include the ID or name of the book you are reserving and try to reserve again")
    elif intent_name == "Reserve Intent - cancel": # Cancel intent, when user cancels reservation attempt
        remove_context(project_id, session_id, 'ReserveIntent-followup')
        current_reservation = {}
        speak("Cancelling your reservation")
    elif intent_name == "Duration Intent":
        parameters = dict(response.query_result.parameters)        
        title = current_reservation.get('title')
        id = current_reservation.get('ID')
        duration = parameters.get('duration', '')
        
        if id is not None and isinstance(id, (float, int)):
            id = int(id)
        
        duration_days = convert_iso_duration_to_days(duration)

        for book in books_dataset:
            if book['ID'] == id:
                start_date = datetime.now()
                end_date = start_date + timedelta(days=duration_days) 
                end_date_str = end_date.strftime("%Y-%m-%d")
                
                book['reserved'] = True
                book['reservation'] = end_date_str
                book['reservedBy'] = userid
                
                speak(f"The book '{book['title']}' has been reserved for {str(duration_days)} days. The return date is {end_date_str}")
                # Update .json file
                with open('books_dataset.json', 'w') as f:
                    json.dump(books_dataset, f, indent=4)
                current_reservation = {}
                break
    elif intent_name == "View Reserved Intent":
        search_results = search_reserved_books_by_userid(userid)
        num_results = len(search_results)
        
        if num_results >= 1:
            print_search_results(search_results)
            speak("Here is your list of reserved books.")
        else:
            speak("You have no books reserved.")
    elif intent_name == "Return Intent":
        parameters = dict(response.query_result.parameters)
        title = parameters.get('title', '')        
        id = parameters.get('id', '')
        if id is not None and isinstance(id, (float, int)):
            id = int(id)
        
        search_results = search_books_by_title_or_id(title, id) 
        num_results = len(search_results)
        print_search_results(search_results)

        if num_results == 1: # Return only if one book found
            if check_reserved(search_results[0]): # Check if book is reserved
                if check_book_by_userid(search_results[0], userid): # Check if book is reserved by userid
                    current_return['title'] = search_results[0]['title']
                    current_return['ID'] = search_results[0]['ID']
                    speak(f"The book '{search_results[0]['title']}' can be returned. Please confirm if you would like to return the book")
                else:
                    speak(f"The book '{search_results[0]['title']}' is reserved by another user. Please try again.")
                    remove_context(project_id, session_id, 'ReturnIntent-followup')
                    current_return = {}  
            else:
                remove_context(project_id, session_id, 'ReturnIntent-followup')
                current_return = {}
                speak(f"The book '{search_results[0]['title']}' cannot be returned because it is not reserved. Please try again")                                               
        elif num_results > 1:
            remove_context(project_id, session_id, 'ReturnIntent-followup')
            current_return = {}
            speak("Multiple books found. Please be more specific.")
        else: 
            remove_context(project_id, session_id, 'ReturnIntent-followup')
            current_return = {}
            speak("There is no book with this ID or name, please include the ID or name of the book you are returning and try to return again")        
    elif intent_name == 'Return Intent - yes': 
        title = current_return.get('title')
        id = current_return.get('ID')
        
        if id is not None and isinstance(id, (float, int)):
            id = int(id)

        for book in books_dataset:
            if book['ID'] == id:
                book['reserved'] = False
                book['reservation'] = None
                book['reservedBy'] = None
                
                speak(f"The book '{book['title']}' has been returned.")
                
                # Update .json file
                with open('books_dataset.json', 'w') as f:
                    json.dump(books_dataset, f, indent=4)
                current_return = {}
                break
    elif intent_name == 'Return Intent - no':
        remove_context(project_id, session_id, 'ReturnIntent-followup')
        current_return = {}
        speak("Keeping your reservation")
    elif intent_name == "FAQ Intent":
        user_query = response.query_result.query_text
        keywords = extract_keywords(user_query)
        answer = find_faq_answer(keywords)
        
        if len(answer) > 1:
            answers_text = "\n\n".join(faq for faq in answer)
            speak("Multiple questions found that fit your query. Here are some answers that might help:")
            print(answers_text)
        elif answer:
            speak("Retrieving response from UTS FAQ")
            print(answer[0])
        else:
            speak("Sorry, I couldn't find an answer to your question.")

    elif intent_name == "Functionalities Intent":
        speak("I can assist with multiple functions:\n1. Search for books provided at least the title, author, or genre of book\n2. Reserve books for 1-10 days given the books title or ID.\n3. View any of your reserved books.\n4. Return any of your reserved books early.\n5. Answer common UTS University FAQs on Admissions, Offers, Enrolment/Course advice, or Student ID cards")
    else:
        speak(response.query_result.fulfillment_text)  
    return 

# Function to extract keywords from text input using spaCy
def extract_keywords(text):
    doc = nlp(text)
    keywords = [token.text for token in doc if token.is_stop != True and token.is_punct != True]
    return keywords

def find_faq_answer(keywords):
    matching_faqs = []
    
    for q in faq:
        if all(keyword.lower() in q['question'].lower() for keyword in keywords):
            formatted_faq = f"Q: {q['question']}\nA: {q['answer']}"
            matching_faqs.append(formatted_faq)
            
    return matching_faqs

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

def search_reserved_books_by_userid(userid=None):
    results = []
    for book in books_dataset:
        if book['reservedBy'] is not None and book['reservedBy'] == userid and book['reserved'] is True:
            results.append(book)
    return results     
        
def check_reserved(book):
    if book['reserved'] is True:
        return True
    return False
   
def check_book_by_userid(book, userid):
    if book['reservedBy'] is not None and book['reservedBy'] == userid:
        return True
    return False

def print_search_results(results):
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
        speak("None of the listed books are available for reservation")
        return
    speak("There are books listed that are available for reservation.")
    
# Function to check current reservations and remove reservations past the due date
def update_expired_reservations():
    for book in books_dataset:
        if book['reserved']:
            reservation_end_date_str = book.get('reservation', '')
            if reservation_end_date_str:
                reservation_end_date = datetime.strptime(reservation_end_date_str, '%Y-%m-%d')
                if reservation_end_date < datetime.now():
                    book['reserved'] = False
                    book['reservation'] = None
                    book['reservedBy'] = None
    # Update json file
    with open('books_dataset.json', 'w') as f:
        json.dump(books_dataset, f, indent=4)
        current_reservation = {}

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
        print("Listening...") # Could change this to show potential commands or something
        audio = recogniser.listen(source, phrase_time_limit=5, timeout=30)
        
        try:
            text = convert_numbers(recogniser.recognize_google(audio).lower())
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            return "I couldn't understand what you said, please try again."
        except sr.RequestError:
            return "I'm having trouble connecting to the speech service."

def validate_user_id(input):
    if input and input.isdigit():
        return str(input)
    else:
        return None

def main():
    global userid
    update_expired_reservations()
    
    #Debug by commenting out this beginning section and manually setting a global userid variable
    speak("Welcome to Library Virtual Assistant")
    speak("Please login with your user id")
    while True:
       userid_input = listen()
       userid = validate_user_id(userid_input)
       
       if "cancel" in userid_input.lower():
           print("Goodbye!")
           sys.exit() 
       if userid is not None:
           print(f"Logged into: {userid}")
           break
       else:
           speak("Invalid input. Try again and ensure your user ID contains only numbers.")
           print("Say 'cancel' to exit the program if you do not know your user id")

    speak("Please speak your query, you can search, reserve, view your reservations, or ask a question if its in the FAQ.")
    speak("Say 'stop listening' if you no longer have queries.")
    
    while True:
        # Listen for commands
        command = listen()
        
        # Debug
        # command = "test input"
        
        
        if 'stop listening' in command:
            print("Goodbye!")
            break
        else: 
            detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
            #command = "yes"
            #detect_intent_texts(project_id, session_id, command, DIALOGFLOW_LANGUAGE_CODE)
            
            # Debug with manual command line
            #break
        
if __name__ == "__main__":
    main()
