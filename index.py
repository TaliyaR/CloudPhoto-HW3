import json
import os
import boto3
import requests

DB_FILE_NAME = os.environ.get('db_file_name')


def handler(event, context):
    AWS_ACESS_KEY_ID = os.environ.get('aws_access_key_id')
    AWS_SECRET_ACESS_KEY = os.environ.get('aws_secret_access_key')
    BUCKET_ID = os.environ.get('bucket_id')
    BOT_TOKEN = os.environ.get('bot_token')
    CHAT_ID = os.environ.get('chat_id')

    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=AWS_ACESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACESS_KEY
    )

    is_message_from_queue = True
    try:
        event['messages'][0]['event_metadata']['event_type']

    except KeyError:
        is_message_from_queue = False

    if is_message_from_queue:
        message_body_json = event['messages'][0]['details']['message']['body']
        message_body = json.loads(message_body_json)

        faces = message_body['faces']
        parent_object = message_body['parentObject']

        for face in faces:
            face_image_response = s3.get_object(Bucket=BUCKET_ID, Key=face)
            face_image_content = face_image_response['Body'].read()
            params = {'chat_id': CHAT_ID, 'caption': parent_object}
            files = {'photo': face_image_content}
            postRequest(BOT_TOKEN, '/sendMessage', json_variable={'chat_id': CHAT_ID, 'text': 'Кто это?'})
            requests.post('https://api.telegram.org/bot{0}/sendPhoto'.format(BOT_TOKEN), data=params, files=files)

    else:
        try:
            body = event['body']
            body_json = json.loads(body)
            message = body_json['message']
            message_id = message['message_id']
        except KeyError:
            message = body_json['edited_message']
            message_id = message['message_id']

        is_valid_reply = False
        photo_id = ""
        photo_name = ""
        try:
            photo_id = message['reply_to_message']['caption']
            if message['reply_to_message']['from']['is_bot'] == True:
                is_valid_reply = True
                photo_name = message['text']

        except KeyError:
            is_valid_reply = False

        if is_valid_reply:
            db_file = {}
            try:
                get_db_file_response = s3.get_object(Bucket=BUCKET_ID, Key=DB_FILE_NAME)
                db_file = json.loads(get_db_file_response['Body'].read())
            except Exception as e:
                db_file = {}

            current_images_for_name = []
            try:
                current_images_for_name = db_file[photo_name]
            except KeyError:
                current_images_for_name = []

            is_append_file = True
            for image in current_images_for_name:
                if image == photo_id:
                    is_append_file = False
            if is_append_file:
                current_images_for_name.append(photo_id)
                db_file[photo_name] = current_images_for_name
                s3.put_object(Body=json.dumps(db_file), Bucket=BUCKET_ID, Key=DB_FILE_NAME)

        else:
            try:
                message_text = message['text']
            except Exception as e:
                postRequest(BOT_TOKEN, '/sendMessage', json_variable={'chat_id': CHAT_ID, 'text': 'Не понимаю!',
                                                                      'reply_to_message_id': message_id})
                return {
                    'statusCode': 200,
                    'body': 'Команда не понятна!',
                }
            command_parts = message_text.split(' ')
            is_command_find = False
            for part in command_parts:
                if part == '/find':
                    is_command_find = True
            if len(command_parts) == 2 and is_command_find:
                name_to_find = command_parts[1]
                try:
                    get_db_file_response = s3.get_object(Bucket=BUCKET_ID, Key=DB_FILE_NAME)
                    db_file = json.loads(get_db_file_response['Body'].read())
                except Exception as e:
                    postRequest(BOT_TOKEN, '/sendMessage', json_variable={'chat_id': CHAT_ID,
                                                                          'text': 'У пользователя с таким именем нет фотографий!',
                                                                          'reply_to_message_id': message_id})
                    return {
                        'statusCode': 200,
                        'body': 'Нет фото!',
                    }
                try:
                    images = db_file[name_to_find]
                except KeyError:
                    postRequest(
                        BOT_TOKEN,
                        '/sendMessage',
                        json_variable={'chat_id': CHAT_ID,
                                       'text': 'У пользователя с таким именем нет фотографий!',
                                       'reply_to_message_id': message_id})
                    return {
                        'statusCode': 200,
                        'body': 'Нет фото!',
                    }
                postRequest(
                    BOT_TOKEN,
                    '/sendMessage',
                    json_variable={'chat_id': CHAT_ID,
                                   'text': f'Фотографии пользователя {name_to_find}:'})

                for image in images:
                    image_response = s3.get_object(Bucket=BUCKET_ID, Key=image)
                    image_response_content = image_response['Body'].read()
                    params = {'chat_id': CHAT_ID}
                    files = {'photo': image_response_content}
                    requests.post('https://api.telegram.org/bot{0}/sendPhoto'.format(BOT_TOKEN), data=params,
                                  files=files)
            else:
                postRequest(
                    BOT_TOKEN,
                    '/sendMessage',
                    json_variable={'chat_id': CHAT_ID,
                                   'text': 'Неизвестная команда! Используйте команду "/find ИМЯ_ПОЛЬЗОВАТЕЛЯ" для поиска фотографий.',
                                   'reply_to_message_id': message_id})
                return {
                    'statusCode': 200,
                    'body': 'Неизвестная команда!',
                }

    return {
        'statusCode': 200,
        'body': 'Ok',
    }


def postRequest(token, method, json_variable):
    return requests.post("https://api.telegram.org/bot" + token + method, json=json_variable)
