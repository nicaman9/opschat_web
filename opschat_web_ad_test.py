import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string
import os
import webbrowser
from PIL import Image, ImageTk, ImageDraw
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urldefrag
# from ldap3 import Server, Connection, ALL, NTLM, Tls, SASL, KERBEROS # Import necessary ldap3 components - Commented out for bypass
import sys
import getpass # To potentially get current username

# --- Configuration ---
# !! IMPORTANT !!
AD_CONFIG = {
    "SERVER": "your_ad_server.your_domain.com",  # e.g., dc01.company.local
    "DOMAIN": "YOUR_DOMAIN",                   # e.g., COMPANY
    "USE_SSL": True,                           # Use True for LDAPS (port 636), False for LDAP (port 389)
    "USERNAME_FORMAT": "{username}@{domain}.com", # Or "{domain}\\{username}" or just "{username}" - Check your AD setup
    # "AUTH_METHOD": NTLM, # Or SASL with KERBEROS, or potentially SIMPLE (less secure) - Commented out for bypass
    "PORT": None # Optional: Specify port if not default (389/636). None uses default.
}

# --- Web Search Configuration ---
TARGET_WEBSITE_URL = "https://www.espn.com" # The website to search
MAX_PAGES_TO_Crawl = 100
REQUEST_TIMEOUT = 10 # Seconds to wait for website response
REQUEST_DELAY = 0.2 # Seconds to wait between requests to be polite

# --- NLTK Setup ---
# Corrected error handling for NLTK downloads
try:
    nltk.data.find('tokenizers/punkt')
#xcept nltk.downloader.DownloadError:
    print("NLTK 'punkt' not found. Downloading...")
    try:
        nltk.download('punkt', quiet=True)
        print("NLTK 'punkt' downloaded successfully.")
    except Exception as e:
        print(f"Error downloading NLTK 'punkt': {e}")
except Exception as e:
    print(f"Error checking NLTK 'punkt': {e}")


try:
    nltk.data.find('corpora/stopwords')
#xcept nltk.downloader.DownloadError: # 
    print("NLTK 'stopwords' not found. Downloading...")
    try:
        nltk.download('stopwords', quiet=True)
        print("NLTK 'stopwords' downloaded successfully.")
    except Exception as e:
        print(f"Error downloading NLTK 'stopwords': {e}")
except Exception as e:
     print(f"Error checking NLTK 'stopwords': {e}")


USE_NLTK = True
# Ensure stopwords are loaded after potential download
try:
    STOP_WORDS = set(stopwords.words('english'))
except LookupError:
    print("Could not load NLTK stopwords. Keyword extraction may be less effective.")
    USE_NLTK = False
    STOP_WORDS = set() # Use an empty set if stopwords fail to load
except Exception as e:
    print(f"An unexpected error occurred loading stopwords: {e}")
    USE_NLTK = False
    STOP_WORDS = set()


# --- Login Window ---
class LoginWindow(simpledialog.Dialog):
    """Modal dialog for AD Login."""
    def __init__(self, parent, title):
        self.username = None
        self.password = None
        super().__init__(parent, title)

    def body(self, master):
        """Creates the body of the login dialog."""
        ttk.Label(master, text="Username:").grid(row=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(master, text="Password:").grid(row=1, sticky=tk.W, padx=5, pady=5)

        self.username_entry = ttk.Entry(master, width=30)
        self.password_entry = ttk.Entry(master, width=30, show="*")

        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # Try to pre-fill username
        try:
            self.username_entry.insert(0, getpass.getuser())
        except Exception:
            pass # Ignore if getting username fails

        return self.username_entry # initial focus

    def validate(self):
        """
        Validates the input and attempts AD authentication.
        Modified to bypass AD authentication for testing.
        """
        username_input = self.username_entry.get().strip()
        password_input = self.password_entry.get() # Don't strip password

        # --- Start Modification for Testing: Bypass AD Authentication ---
        # if not username_input or not password_input:
        #     messagebox.showwarning("Login Error", "Username and password cannot be empty.", parent=self)
        #     return 0 # Keep dialog open
        #
        # # Attempt AD Authentication
        # if self.authenticate_ad(username_input, password_input):
        #     self.username = username_input # Store username if needed later
        #     self.password = password_input # Store password (use cautiously!)
        #     return 1 # Close dialog, apply will be called
        # else:
        #     # Error message is shown within authenticate_ad
        #     return 0 # Keep dialog open

        # Bypass authentication for testing purposes
        self.username = username_input if username_input else "generic_test_user" # Use entered username if available, else generic
        self.password = password_input if password_input else "generic_test_password" # Use entered password if available, else generic
        print("AD Authentication bypassed for testing.")
        return 1 # Close dialog, proceed as if successful
        # --- End Modification for Testing ---

    def apply(self):
        """Called when validate returns 1."""
        # Credentials are valid (or bypassed), stored in self.username and self.password
        print("Login successful (AD authentication bypassed for testing).")
        pass # Nothing more to do here, main app will proceed

    # Comment out or remove the authenticate_ad method if you don't want it present at all during testing
    # def authenticate_ad(self, username, password):
    #     """Attempts to authenticate against Active Directory."""
    #     # This method is bypassed in the modified validate method
    #     print("authenticate_ad method called, but authentication is bypassed.")
    #     return True # Simulate successful authentication


# --- Main Chatbot Application ---
class ChatbotApp:
    def __init__(self, root):
        print("ChatbotApp: Initializing...")
        self.root = root
        self.root.title("Operations Chatbot")
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        # Placeholder for background image setup
        self.bg_image = None
        self.bg_label = None
        self.profile_image = None
        self._load_images() # Load images if available

        # Initialize chat history
        self.chat_history = []
        self.all_results = [] # Store current web search results

        self.bot_name = "Rocky" # Bot name

        self.setup_gui()
        print("ChatbotApp: Initialization complete.")


    def _load_images(self):
        """Loads UI images, handling potential errors."""
        print("ChatbotApp: Loading images...")
        try:
            # Load and resize the background image
            # Ensure this file exists in the same directory as the script
            bg_image_path = "yellowjacketlogo.png"
            if os.path.exists(bg_image_path):
                bg_image_pil = Image.open(bg_image_path)
                bg_image_pil = bg_image_pil.resize((800, 600), Image.LANCZOS)

                # Create a semi-transparent overlay
                overlay = Image.new('RGBA', (800, 600), (255, 255, 255, 77)) # 30% opacity

                # Composite the images
                bg_image_pil = bg_image_pil.convert('RGBA')
                bg_image_pil = Image.alpha_composite(bg_image_pil, overlay)

                self.bg_image = ImageTk.PhotoImage(bg_image_pil)
                print(f"ChatbotApp: Loaded background image from {bg_image_path}")
            else:
                 print(f"Warning: Background image file not found at {bg_image_path}. Background will be empty.")
                 self.bg_image = None


            # Load profile image for the bot
            profile_img_path = "yellowjacketlogo.png" # Ensure this file exists
            if os.path.exists(profile_img_path):
                profile_img_pil = Image.open(profile_img_path)
                profile_img_pil = profile_img_pil.resize((40, 40), Image.LANCZOS)
                mask = Image.new('L', (40, 40), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, 40, 40), fill=255)
                output = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
                output.paste(profile_img_pil, (0, 0), mask=mask) # Use mask parameter
                self.profile_image = ImageTk.PhotoImage(output)
                print(f"ChatbotApp: Loaded profile image from {profile_img_path}")
            else:
                print(f"Warning: Profile image file not found at {profile_img_path}. Profile image will be empty.")
                self.profile_image = None


        except FileNotFoundError:
            # This block might not be reached with os.path.exists checks, but kept as a fallback
            print("Warning: Image file(s) not found. Images will not be loaded.")
            self.bg_image = None
            self.profile_image = None
        except Exception as e:
            print(f"Warning: Could not load images: {e}")
            self.bg_image = None
            self.profile_image = None
        print("ChatbotApp: Image loading finished.")


    def setup_gui(self):
        """Sets up the main graphical user interface."""
        print("ChatbotApp: Setting up GUI...")
        # Background Label
        if self.bg_image:
            self.bg_label = tk.Label(self.root, image=self.bg_image)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            print("ChatbotApp: Background image placed.")
        else:
            print("ChatbotApp: No background image to place.")


        # Main frame (ensure it's on top of the background)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.95, relheight=0.95) # Center frame
        # Make frame background transparent (or match background) if needed
        # main_frame.configure(style='TFrame') # May need custom style for transparency
        print("ChatbotApp: Main frame created and placed.")

        # Configure grid weights for main_frame
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=0)  # Title row
        main_frame.rowconfigure(1, weight=1)  # Chat display row
        main_frame.rowconfigure(2, weight=0)  # Input frame row
        main_frame.rowconfigure(3, weight=0)  # Buttons frame row
        print("ChatbotApp: Main frame grid configured.")

        # --- Title Frame ---
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        title_frame.columnconfigure(0, weight=1)
        print("ChatbotApp: Title frame created.")

        title_label = ttk.Label(title_frame, text="Ops Chatbot", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, sticky=tk.W)
        print("ChatbotApp: Title label created.")

        clear_chat_button = ttk.Button(title_frame, text="Clear Chat", command=self.clear_chat)
        clear_chat_button.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
        print("ChatbotApp: Clear Chat button created.")

        # --- Chat Display ---
        self.chat_display = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=80, height=20, state=tk.DISABLED) # Start disabled
        self.chat_display.grid(row=1, column=0, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.chat_display.tag_configure("user", foreground="blue", font=("Arial", 10, "bold"))
        self.chat_display.tag_configure("bot", foreground="green", font=("Arial", 10, "bold"))
        self.chat_display.tag_configure("link", foreground="purple", underline=1, font=("Arial", 10))
        self.chat_display.tag_configure("snippet", foreground="#333333", font=("Arial", 10)) # Style for snippet
        self.chat_display.tag_configure("title", foreground="#111111", font=("Arial", 10, "bold")) # Style for title

        self.chat_display.tag_bind("link", "<Button-1>", self.handle_link_click_event) # Corrected binding
        self.chat_display.tag_bind("link", "<Enter>", lambda e: self.chat_display.config(cursor="hand2"))
        self.chat_display.tag_bind("link", "<Leave>", lambda e: self.chat_display.config(cursor=""))
        print("ChatbotApp: Chat display created and configured.")

        # --- Input Frame ---
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(0, weight=1)
        print("ChatbotApp: Input frame created.")

        input_label = ttk.Label(input_frame, text=f"Ask a question or search for keywords:", font=("Arial", 10))
        input_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 5))
        print("ChatbotApp: Input label created.")

        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(input_frame, textvariable=self.message_var, width=70)
        self.message_entry.grid(row=1, column=0, padx=5, sticky=(tk.W, tk.E))
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        print("ChatbotApp: Message entry created.")

        send_button = ttk.Button(input_frame, text="Search", command=self.send_message)
        send_button.grid(row=1, column=1, padx=5)
        print("ChatbotApp: Send button created.")

        clear_button = ttk.Button(input_frame, text="Clear Input", command=self.clear_input)
        clear_button.grid(row=1, column=2, padx=5)
        print("ChatbotApp: Clear Input button created.")

        # --- Buttons Frame (Optional - kept for structure, buttons removed/repurposed) ---
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        print("ChatbotApp: Buttons frame created.")

        # Example: Add a button to show missing info modal
        missing_link = ttk.Label(buttons_frame, text="Report Issue?", foreground="darkblue", cursor="hand2")
        missing_link.pack(side=tk.LEFT, padx=5)
        missing_link.bind("<Button-1>", self.show_missing_modal)
        print("ChatbotApp: Report Issue link created.")
        
        missing_link_2 = ttk.Label(buttons_frame, text="Ticket Creator", foreground="darkblue", cursor="hand2")
        missing_link_2.pack(side=tk.LEFT, padx=25)
        missing_link_2.bind("<Button-1>", self.show_missing_modal)

        missing_link_3 = ttk.Label(buttons_frame, text="Procedures", foreground="darkblue", cursor="hand2")
        missing_link_3.pack(side=tk.LEFT, padx=25)
        missing_link_3.bind("<Button-1>", self.show_missing_modal)
        
        # --- Initial Welcome Message ---
        self.add_bot_message(f"Hello! How can I help?")
        self.message_entry.focus()
        print("ChatbotApp: Welcome message added and input focused.")
        print("ChatbotApp: GUI setup complete.")


    def clear_input(self):
        """Clears the message input field."""
        self.message_var.set("")
        self.message_entry.focus()

    def send_message(self):
        """Handles sending a user message (initiates search)."""
        message = self.message_var.get().strip()
        if not message:
            messagebox.showwarning("Input Error", "Please enter keywords to search for.")
            return

        self.add_user_message(message)
        self.clear_input()
        self.process_message(message) # Trigger the search and response

    def add_message_to_display(self, sender, message, tags=None):
        """Adds a message block (user or bot) to the chat display."""
        self.chat_display.config(state=tk.NORMAL)
        insert_point = tk.END

        # Add profile image for bot messages
        if sender == self.bot_name and self.profile_image:
            # Create a small frame to hold the image and align text
            line_frame = tk.Frame(self.chat_display, bg=self.chat_display.cget('bg')) # Match background
            profile_label = tk.Label(line_frame, image=self.profile_image, bg=self.chat_display.cget('bg'))
            profile_label.pack(side=tk.LEFT, anchor='nw', padx=(0, 5)) # Anchor top-left

            # Add frame to text widget
            self.chat_display.window_create(insert_point, window=line_frame, padx=5, pady=2)
            # Insert sender name after the image frame
            self.chat_display.insert(insert_point, f"{sender}: ", ("bot",))
            insert_point = self.chat_display.index(f"{insert_point}+1c") # Move past the image frame for text
        elif sender == "You":
             self.chat_display.insert(insert_point, f"{sender}: ", ("user",))
        else: # Generic bot message without image
             self.chat_display.insert(insert_point, f"{sender}: ", ("bot",))


        # Insert the actual message content
        if isinstance(message, list): # Handle structured messages (like search results)
            for item in message:
                text = item.get("text", "")
                tag_list = item.get("tags", [])
                self.chat_display.insert(tk.END, text, tuple(tag_list)) # Apply tags
        else: # Simple text message
            self.chat_display.insert(tk.END, message)

        self.chat_display.insert(tk.END, "\n\n") # Add spacing after message block
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def add_user_message(self, message):
        """Adds a user message to the display."""
        self.add_message_to_display("You", message)
        self.chat_history.append({"sender": "user", "text": message})

    def add_bot_message(self, message):
        """Adds a simple bot message to the display."""
        self.add_message_to_display(self.bot_name, message)
        self.chat_history.append({"sender": "bot", "text": message})

    def add_bot_search_results(self, results):
        """Formats and adds search results from the bot."""
        self.chat_display.config(state=tk.NORMAL)
        insert_point = tk.END

        # Add profile image and bot name
        if self.profile_image:
            line_frame = tk.Frame(self.chat_display, bg=self.chat_display.cget('bg'))
            profile_label = tk.Label(line_frame, image=self.profile_image, bg=self.chat_display.cget('bg'))
            profile_label.pack(side=tk.LEFT, anchor='nw', padx=(0, 5))
            self.chat_display.window_create(insert_point, window=line_frame, padx=5, pady=2)
        self.chat_display.insert(insert_point, f"{self.bot_name}: ", ("bot",))

        # Display best result
        best_result = results[0]
        self.chat_display.insert(tk.END, "Here's the most relevant result I found:\n")
        self.chat_display.insert(tk.END, f"Title: {best_result['title']}\n", ("title",))
        # Make URL clickable
        link_tag_best = f"link_{0}" # Index 0 for the best result
        self.chat_display.insert(tk.END, f"URL: {best_result['url']}\n", ("link", link_tag_best))
        self.chat_display.tag_bind(link_tag_best, "<Button-1>", lambda e, idx=0: self.handle_link_click_event(e, idx))
        self.chat_display.tag_bind(link_tag_best, "<Enter>", lambda e: self.chat_display.config(cursor="hand2"))
        self.chat_display.tag_bind(link_tag_best, "<Leave>", lambda e: self.chat_display.config(cursor=""))

        self.chat_display.insert(tk.END, f"Relevant Section Snippet:\n{best_result['snippet']}\n\n", ("snippet",))

        # Display other links
        if len(results) > 1:
            self.chat_display.insert(tk.END, "Other relevant pages found:\n")
            for i, result in enumerate(results[1:], start=1): # Start index from 1 for others
                link_tag = f"link_{i}"
                link_text = f"\u27a4 {result['title']} ({result['url']})\n" # Include URL in link text
                self.chat_display.insert(tk.END, link_text, ("link", link_tag))
                # Bind click event with correct index
                self.chat_display.tag_bind(link_tag, "<Button-1>", lambda e, idx=i: self.handle_link_click_event(e, idx))
                self.chat_display.tag_bind(link_tag, "<Enter>", lambda e: self.chat_display.config(cursor="hand2"))
                self.chat_display.tag_bind(link_tag, "<Leave>", lambda e: self.chat_display.config(cursor=""))


        self.chat_display.insert(tk.END, "\n\n") # Spacing
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        # Add results to history (optional, could be large)
        # self.chat_history.append({"sender": "bot", "results": results})

    def process_message(self, message):
        """Processes user message: extracts keywords and initiates web search."""
        keywords = self.extract_keywords(message)
        if not keywords:
            self.add_bot_message("Could not extract keywords. Please try different terms.")
            return

        self.add_bot_message(f"Searching...")
        self.root.update_idletasks() # Update UI to show searching message

        try:
            search_results = self.search_website(TARGET_WEBSITE_URL, keywords)
            self.all_results = search_results # Store current results

            if search_results:
                self.add_bot_search_results(search_results)
            else:
                self.add_bot_message(f"I couldn't find any relevant information on {TARGET_WEBSITE_URL} for those keywords.")

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error searching website: {e}"
            print(error_msg)
            self.add_bot_message(f"Sorry, I encountered a network error trying to search the website. Please check your connection. ({e})")
        except Exception as e:
            error_msg = f"An unexpected error occurred during search: {e}"
            print(error_msg)
            self.add_bot_message(f"Sorry, an unexpected error occurred while searching: {e}")

    def extract_keywords(self, message):
        """Extracts keywords from a message using NLTK."""
        if not USE_NLTK:
            # Basic fallback if NLTK fails
            return [word for word in message.lower().split() if len(word) > 2]

        try:
            tokens = word_tokenize(message.lower())
            keywords = [word for word in tokens if word.isalnum() and word not in STOP_WORDS]
            return keywords
        except Exception as e:
            print(f"Warning: NLTK keyword extraction failed: {e}")
            # Fallback to basic tokenization
            return [word for word in message.lower().split() if len(word) > 2]

    def search_website(self, base_url, keywords):
        """Crawls and searches the website for keywords."""
        results = []
        visited_urls = set()
        urls_to_visit = {base_url}
        session = requests.Session() # Use a session for potential connection pooling

        print(f"Starting search on {base_url} for keywords: {keywords}")

        while urls_to_visit and len(visited_urls) < MAX_PAGES_TO_Crawl:
            current_url = urls_to_visit.pop()

            # Normalize URL (remove fragment) and check if visited
            current_url_norm, _ = urldefrag(current_url)
            if current_url_norm in visited_urls:
                continue

            # Ensure we stay on the target site (basic check)
            if not current_url_norm.startswith(base_url):
                continue

            visited_urls.add(current_url_norm)
            print(f"Visiting ({len(visited_urls)}/{MAX_PAGES_TO_Crawl}): {current_url_norm}")

            try:
                response = session.get(current_url_norm, timeout=REQUEST_TIMEOUT, headers={'User-Agent': 'OpsChatbot/1.0'})
                response.raise_for_status() # Raise HTTPError for bad responses

                # Only process HTML content
                if 'text/html' not in response.headers.get('Content-Type', '').lower():
                    print(f"Skipping non-HTML content at {current_url_norm}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # --- Find new links on the same domain ---
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    try:
                        # Construct absolute URL
                        full_url = urljoin(current_url_norm, href)
                        full_url_norm, _ = urldefrag(full_url)

                        # Check if it's within the target site and not visited/queued
                        if full_url_norm.startswith(base_url) and \
                           full_url_norm not in visited_urls and \
                           full_url_norm not in urls_to_visit:
                             urls_to_visit.add(full_url_norm)
                    except Exception as link_e:
                        print(f"Could not process link '{href}' on page {current_url_norm}: {link_e}")


                # --- Search for keywords in the page text ---
                page_text = soup.get_text(separator=' ', strip=True).lower()
                match_count = sum(keyword in page_text for keyword in keywords)

                if match_count > 0:
                    # Find a snippet
                    snippet = f"Found {match_count} keyword(s)." # Default
                    first_match_p = None
                    # Prioritize paragraphs, then headings, then list items
                    for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'li', 'div']):
                        p_text_lower = p.get_text(strip=True).lower()
                        if any(keyword in p_text_lower for keyword in keywords):
                            first_match_p = p
                            break

                    if first_match_p:
                         # Try to get a reasonable amount of context
                         snippet_text = first_match_p.get_text(separator=' ', strip=True)
                         # Limit snippet length gracefully
                         snippet = (snippet_text[:250] + '...') if len(snippet_text) > 253 else snippet_text
                    elif soup.title: # Fallback to title if no good paragraph found
                        snippet = soup.title.string.strip()[:250] + "..."

                    results.append({
                        'url': current_url_norm,
                        'title': soup.title.string.strip() if soup.title else "No Title Found",
                        'snippet': snippet.strip(),
                        'score': match_count # Simple relevance score
                    })

                time.sleep(REQUEST_DELAY) # Be polite

            except requests.exceptions.Timeout:
                 print(f"Timeout fetching {current_url_norm}")
            except requests.exceptions.RequestException as e:
                print(f"Error fetching {current_url_norm}: {e}")
            except Exception as e:
                 print(f"Error processing {current_url_norm}: {e}") # Catch other parsing errors etc.


        # Sort results by score (descending)
        results.sort(key=lambda x: x['score'], reverse=True)
        print(f"Search finished. Found {len(results)} relevant pages.")
        return results

    def handle_link_click_event(self, event, index):
        """Handles clicks on link tags in the chat display."""
        if 0 <= index < len(self.all_results):
            url_to_open = self.all_results[index]['url']
            print(f"Opening link index {index}: {url_to_open}")
            try:
                webbrowser.open(url_to_open)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open link:\n{url_to_open}\n\nError: {e}")
                print(f"Error opening link {url_to_open}: {e}")
        else:
            print(f"Error: Invalid link index {index} clicked.")

    # --- Kept Helper Functions (Clear Chat, Missing Modal) ---

    def clear_chat(self):
        """Clears the chat display and resets history."""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_history = []
        self.all_results = []
        # Add welcome message back
        self.add_bot_message(f"Chat cleared. How can I help?")

    def show_missing_modal(self, event=None):
        """Shows a modal window to report missing info/issues via email."""
        # Simple Toplevel window for reporting
        modal_window = tk.Toplevel(self.root)
        modal_window.title("Report Issue / Missing Info")
        modal_window.geometry("400x300")
        modal_window.resizable(False, False)
        modal_window.transient(self.root) # Keep on top of main window
        modal_window.grab_set() # Make modal

        # Center window
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        modal_w = 400
        modal_h = 300
        x_pos = main_x + (main_w - modal_w) // 2
        y_pos = main_y + (main_h - modal_h) // 2
        modal_window.geometry(f"{modal_w}x{modal_h}+{x_pos}+{y_pos}")


        ttk.Label(modal_window, text="Please describe the issue or missing information:").pack(pady=10, padx=10, anchor='w')
        missing_text = scrolledtext.ScrolledText(modal_window, wrap=tk.WORD, width=45, height=10)
        missing_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        missing_text.focus()

        button_frame = ttk.Frame(modal_window)
        button_frame.pack(pady=10)

        def submit_report():
            message = missing_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("Input Error", "Please enter a description.", parent=modal_window)
                return
            # Call the email sending function (ensure it's defined or imported)
            self.send_email_report(message, modal_window)

        submit_button = ttk.Button(button_frame, text="Submit Report", command=submit_report)
        submit_button.pack(side=tk.LEFT, padx=5)

        close_button = ttk.Button(button_frame, text="Cancel", command=modal_window.destroy)
        close_button.pack(side=tk.LEFT, padx=5)

    def send_email_report(self, message, modal_window):
        """Sends the report via email (configure sender/receiver)."""
        # --- Email Configuration (Replace with your details or use a config file) ---
        SENDER_EMAIL = "your_sender_email@example.com" # Replace
        SENDER_PASSWORD = "your_sender_password"       # Replace (use App Password for Gmail)
        RECEIVER_EMAIL = "admin_or_support_email@example.com" # Replace
        SMTP_SERVER = "smtp.example.com"             # Replace (e.g., smtp.gmail.com)
        SMTP_PORT = 587                              # Replace (e.g., 587 for TLS, 465 for SSL)
        # --- End Email Configuration ---

        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = "Ops Chatbot Issue Report"

            body = f"Issue/Missing Information Report from Ops Chatbot:\n\nUser reported:\n{message}"
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls() # Use TLS
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()

            messagebox.showinfo("Success", "Report submitted successfully!", parent=modal_window)
            modal_window.destroy()

        except Exception as e:
            error_msg = f"Failed to send report via email: {e}"
            print(error_msg)
            messagebox.showerror("Email Error", f"Failed to send report: {e}\nPlease contact support manually.", parent=modal_window)


# --- Main Execution ---
if __name__ == "__main__":
    print("Script started.")
    root = tk.Tk()
    root.withdraw() # Hide the main window initially
    print("Tkinter root window created and hidden.")

    # Show login dialog
    print("Showing login dialog...")
    try:
        login_dialog = LoginWindow(root, "AD Login Required")
        print("Login dialog closed.")
    except Exception as e:
        print(f"Error during LoginWindow creation or while dialog was open: {e}")
        root.destroy()
        sys.exit()


    # login_dialog.username and login_dialog.password are set if successful (or bypassed)

    if login_dialog.username: # Check if login was successful (apply was called)
        print(f"Login successful (or bypassed) for user: {login_dialog.username}. Proceeding to main app.")
        try:
            root.deiconify() # Show the main window
            print("Main window deiconified.")
            app = ChatbotApp(root)
            print("ChatbotApp instance created.")
            root.mainloop()
            print("Tkinter main loop finished.")
        except Exception as e:
            print(f"Error during main application setup or execution: {e}")
            messagebox.showerror("Application Error", f"An error occurred while starting the application: {e}\nCheck the console for details.")
            root.destroy()
            sys.exit()
    else:
        print("Login cancelled or failed. Exiting.")
        root.destroy() # Destroy the hidden root window if login fails/cancels
        sys.exit()
