from datetime import datetime
import json
import logging
import re
from bs4 import BeautifulSoup
import requests
import os

import azure.functions as func

ALLOWED_SITES=[
    {
        "name":"Virginia Golf Club",
        "url":"https://www.virginiagolf.com.au/"
    },
    {
        "name":"Keperra Golf Club",
        "url":"https://www.keperragolf.com.au/"
    },
    {
        "name":"Pine Rivers Golf Club",
        "url":"https://pinerivers.miclub.com.au/"
    },
]

def get_time(obj):
    time_str = obj["time"]
    return datetime.strptime(time_str, "%I:%M %p")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    date = req.params.get('date')
    if not date:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            date = req_body.get('date')

    if date:
        # Begin our scraping
        results = []
        for website in ALLOWED_SITES:
            try:
                # Step 1: Get the ID from the first URL
                id_url = f"{website['url']}/guests/bookings/ViewPublicCalendar.msp?selectedDate={date}"
                id_response = requests.get(id_url)
                id_data = BeautifulSoup(id_response.content, 'html.parser')

                # Select via css
                id_groups = id_data.select('div.feeGroupRow.nineHole')
                if not id_groups:
                    logging.warning(f"No object found with CSS selector 'div.feeGroupRow.nineHole' on {website}")
                    continue

                # For each matching row
                for id_group in id_groups:
                    class_attribute = ' '.join(id_group.get('class')) # type: ignore

                    class_number = re.search(r"feeGroupId-(\d+)", class_attribute)

                    if class_number:
                        class_number = class_number.group(1)

                    # Step 2: Access the second URL using the obtained ID
                    data_url = f"{website['url']}/guests/bookings/ViewPublicTimesheet.msp?selectedDate={date}&feeGroupId={class_number}"
                    print(data_url)
                    data_response = requests.get(data_url)
                    data_soup = BeautifulSoup(data_response.content, 'html.parser')
                    # Grab the parsed site from metadata
                    rows = data_soup.select('div.row.row-time')
                    print(len(rows))
                    for row in rows:
                        # Extract time
                        time = row.select_one('.time-wrapper h3').text.strip() # type: ignore
                        tees = row.select_one('.time-wrapper h4').text.strip() # type: ignore
                        # Extract price
                        price = row.select_one('.price').text.strip() # type: ignore
                        # Extract number of available slots
                        slots_available = len(row.select('.cell-available'))

                        if not "Foot Golf" in str(tees):
                            results.append({
                                "site":website,
                                "date": date,
                                "time": time,
                                "slots_available": slots_available,
                                "price": price if price else ""
                            })
            except Exception as e:
                logging.error(f"An error occurred while scraping {website}: {str(e)}")

        # Sort by time asc
        results = sorted(results, key=get_time)
        return func.HttpResponse(
            json.dumps(results),
            mimetype="application/json",
        )
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )