import streamlit as st
import google.generativeai as genai
from PIL import Image
from PyPDF2 import PdfReader
from supabase import create_client, Client 
from postgrest.exceptions import APIError


import gspread

import os
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_JSON = os.getenv('CREDENTIALS_JSON')
SHEET_KEY=os.getenv('SHEET_KEY')
GEMINI_KEY=os.getenv('GEMINI_KEY')
SUPABASE_KEY=os.getenv('SUPERBASE_KEY')
SUPABASE_URL=os.getenv('SUPERBASE_URL')

supabase : Client = create_client(SUPABASE_URL,SUPABASE_KEY)


gc = gspread.service_account(filename=CREDENTIALS_JSON)
sheet = gc.open_by_key(SHEET_KEY)
worksheet = sheet.sheet1


# Ensure the API key is configured
genai.configure(api_key=GEMINI_KEY)
model1 = genai.GenerativeModel('gemini-pro')
model2 = genai.GenerativeModel('gemini-pro-vision')

# Function to get the response for PDF input
def get_gemini_response_pdf(input_prompt, context):
    response = model1.generate_content([context, input_prompt])
    return response.text

# Function to get the response for image input
def get_gemini_response_image(input, image, prompt):
    response = model2.generate_content([input, image[0], prompt])
    return response.text

# Function to extract text from PDF
def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

# Function to set up image data for processing
def input_image_setup(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        image_parts = [{"mime_type": uploaded_file.type, "data": bytes_data}]
        return image_parts
    else:
        raise FileNotFoundError("No file uploaded")


input_prompt = """
               You are an expert in understanding invoices.
               You will receive input images as invoices & text
               you will have to answer questions based on the input image
               """

def main():
    st.set_page_config(page_title="Gemini Demo")
    st.header("Gemini Application")

    input = '''give me the details of the invoice like invoice name, invoice number as a integer,invoice company, date, total amount as a integer , no of items as a integer, 
    i need only these fields do not give me any extra details ok?  
    if any field is not available, return them as NULL,
    i need all detials as a python dictionary  '''

    # Dynamic rows to store details
    details = []

    uploaded_file = st.file_uploader("Upload an image or PDF...", type=["jpg", "jpeg", "png", "pdf"])
    submit = st.button("Tell me about it")

    if uploaded_file is not None:
        if uploaded_file.type.startswith('image/'):
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image.", use_column_width=True)
            image_data = input_image_setup(uploaded_file)
            response = get_gemini_response_image(input_prompt, image_data, input)
        elif uploaded_file.type == 'application/pdf':
            st.write("Uploaded PDF:", uploaded_file.name)
            image = None
            context = get_pdf_text([uploaded_file])
            response = get_gemini_response_pdf(input, context)
        else:
            raise ValueError("Unsupported file type.")

        if submit:
            details = []
            st.subheader("The Response is")
            response = response.replace("python","")
            print(response)

            respons_lst = response.split("\n")
            # for x in response:
            #     respons_lst.append(x)
            print(respons_lst)
            for i in respons_lst[:-1]:
                if i not in ['{','}',"'","```"]:
                    details.append(i)
            details.pop(0)
            details = [str(x) for x in details]
            st.write(response)
            print(details)
            response_dict = {}
            for x in details:
                key,val = x.split(':',1)
                key = key.strip().strip('"')
                key=key.replace(":","")
                val=val.replace(",","")
                print(key," corresponding value is ",val)
                response_dict[key] = val
            
            # Split the response by newline characters to separate key-value pairs
            # pairs = response.strip().split('\n')

            # # Initialize an empty dictionary to store key-value pairs
            # response_dict = {}

            # # Iterate over key-value pairs and add them to the dictionary
            # for pair in pairs:
            #     # Split each pair by the first occurrence of the colon
            #     key, value = pair.split(':', 1)

            #     # Remove leading and trailing whitespace and quotes from the key and value
            #     key = key.strip().strip('"')
            #     value = value.strip()

            #     # Handle special cases like null values
            #     if value.lower() == 'null':
            #         value = None
            #     else:
            #         # Remove leading and trailing quotes from the value if present
            #         value = value.strip('"')

            #     # Add the key-value pair to the dictionary
            #     response_dict[key] = value

            # print(response_dict)
            values = []
            for key, value in response_dict.items():
                value = value.replace('"', "")
                st.text_input(key, value)
                values.append(value)
            worksheet.append_row(values)
                
            print(response_dict)
            try:
                supabase.table("Invoices").insert({
                    "invoice_id": int(response_dict['invoice_number']), 
                    "invoice_name": response_dict['invoice_name'],
                    # "date":response_dict['date'], 
                    "invoice_company":response_dict['invoice_company'],
                    "invoice_no": int(response_dict['invoice_number']),   
                    "total_amount":int(response_dict['total_amount']),  
                    "no_of_items":int(response_dict['no_of_items'])
                }).execute()
            except APIError as e:
                if '23505' in str(e): 
                    st.error('This invoice has already been uploaded.')
                else:
                    raise  

# ...

if __name__ == "__main__":
    main()
