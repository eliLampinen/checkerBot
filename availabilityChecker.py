import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
import time
import random
from configFile import (email_sender, email_password, email_receivers, email_subject,
                     availability_file, error_log_path, info_log_path,
                     base_url, availability_update_message, from_hour, to_hour, admin_email)

ERROR_THRESHOLD = 10
DAYS_TO_ITERATE = 5

def log_error(message):
    """Append an error message to the error log file."""
    with open(error_log_path, "a") as error_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_file.write(f"[{timestamp}] {message}\n")

def log_info(message):
    """Append an info message to the info log file."""
    with open(info_log_path, "a") as error_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_file.write(f"[{timestamp}] {message}\n")

def load_availability():
    """
    Load previously sent messages to that if the polled thing is available multiple times
    in a row, not multiple emails are sent for same reason.
    """
    try:
        if os.path.exists(availability_file):
            with open(availability_file, 'r') as file:
                return json.load(file)
        return {}
    except Exception as e:
        log_error(f"Error loading availability: {e}")
        return {}

def save_availability(availability):
    try:
        with open(availability_file, 'w') as file:
            json.dump(availability, file, indent=4)
    except Exception as e:
        log_error(f"Error saving availability: {e}")

def send_email(slots):
    """
    Send email to the customer. Create the body from slots argument. 
    """
    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = ", ".join(email_receivers)
    msg['Subject'] = email_subject
    
    formatted_slots = []
    last_date = ""
    for slot in slots:
        date = slot.split(" - ")[0]
        if date != last_date:
            if last_date:
                formatted_slots.append("")
            last_date = date
        formatted_slots.append(slot)

    body = availability_update_message + '\n'.join(formatted_slots)
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        server.sendmail(email_sender, email_receivers, msg.as_string())
        log_info(f"Email sent successfully: {slots}")
    except Exception as e:
        log_error(f"Failed to send email: {e}")
    finally:
        server.quit()

def has_recent_errors():
    """
    Check if there are more than a specified number of errors logged in the past specified hours.
    """
    now = datetime.now()
    recent_errors_count = 0
    
    try:
        with open(error_log_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        timestamp_str = line.split("]")[0].strip("[")
                        error_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        if now - timedelta(hours=24) <= error_timestamp:
                            recent_errors_count += 1
                            if recent_errors_count > ERROR_THRESHOLD:
                                return True
                    except ValueError:
                        # If the line doesn't match the format, skip it
                        continue
        return False
    except Exception as e:
        log_error(f"An error occurred while reading the log file: {e}")
        return False

def alert_admin_for_constant_errors():
    """
    Alert admin user for constant errors
    """
    msg = MIMEMultipart()
    msg['From'] = email_sender
    msg['To'] = ", ".join(admin_email)
    msg['Subject'] = "Availability script might be broken!"

    body = f"More than {ERROR_THRESHOLD} errors occured in the past 24 hours with the availability script, check the logs."
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(email_sender, email_password)
        server.sendmail(email_sender, admin_email, msg.as_string())
        log_info(f"Admin user alerted for constant errors.")
    except Exception as e:
        log_error(f"Failed to send email: {e}")
    finally:
        server.quit()

def check_availability():
    """
    Check the availability of the thing by reading the HTML with BeautifulSoup. 
    Check DAYS_TO_ITERATE amount of days including today. 
    """
    # Log on avg once per hour
    if random.randint(0, 11) == 9:
        log_info("Starting to run")
    previous_availability = load_availability()
    current_availability = {}
    slots_to_email = []

    for day in range(DAYS_TO_ITERATE):
        time.sleep(5) # Dont spam too hard the server, just in case
        date = (datetime.now() + timedelta(days=day)).strftime('%d.%m.%Y')
        url = f'{base_url}{date}'
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
            else:
                log_error(f"HTTP error {response.status_code} for URL: {url}")
                continue
        except Exception as e:
            log_error(f"Request failed for URL: {url}, error: {e}")
            continue

        try:
            schedule_rows = soup.find_all('tr', class_=['state_F', 'state_R'])
            
            for row in schedule_rows:
                time_slot = row.find('th', class_='datarow').text.strip()
                hour = int(time_slot.split(':')[0])
                if from_hour <= hour < to_hour:
                    cells = row.find_all('td')
                    for index, cell in enumerate(cells, start=1):
                        slot_identifier = f"{date} - Court {index}: {time_slot}"
                        if 'res_success' in cell.get('class', []):
                            current_availability[slot_identifier] = "available"
                            if slot_identifier not in previous_availability:
                                slots_to_email.append(slot_identifier)
        except Exception as e:
            log_error(f"Error processing HTML content from URL: {url}, error: {e}")

    for slot in list(previous_availability):
        if slot not in current_availability:
            del previous_availability[slot]

    save_availability(current_availability)

    if slots_to_email:
        send_email(slots_to_email)

    if has_recent_errors():
        alert_admin_for_constant_errors()

if __name__ == "__main__":
    check_availability()
