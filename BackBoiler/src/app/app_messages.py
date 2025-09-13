import requests
from app import settings

app_id = settings.APP_NAME

def send_message_to_server(from_user='admin', from_user_id=0, to_user='', to_user_id=0, 
                           title='', body='', message_type='message', message_class='page', message_device='telegram', 
                           is_html=False, tag=''):
    from SsoModel.models import AppServiceProvider
    from LogModel.log_handler import print_log
    
    asp = AppServiceProvider.get_active_asp_by_service_core(service_core='message')
    if not asp:
        print_log(level='error', message='no active asp for message service', exception_type='AspError', file_path=__file__, line_number=0, view_name='send_message_to_server')
        return {'return': False, 'error': 'no active asp for message service'}
    
    app_base_url = asp.url()
    app_token = asp.app_token
    
    url = f"{app_base_url}/msgCore/SendMessage"
    
    headers = {
        'Authorization': f'{app_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'app_id': app_id,
        'from_user': from_user,
        'from_user_id': from_user_id,
        'to_user': to_user,
        'to_user_id': to_user_id,
        'title': title,
        'body': body,
        'message_type': message_type,
        'message_class': message_class,
        'message_device': message_device,
        'is_html': is_html,
        'language': 'fa',
        'tag': tag
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        return response.json()
    except Exception as e:
        print_log(level='error', message=f'error sending message app_id:{app_id}-from_user:{from_user}-to_user:{to_user}: ' + str(e), exception_type='MessageError', file_path=__file__, line_number=0, view_name='send_message_to_server')
        return {'return': False, 'error': 'error sending message app_id:{app_id}-from_user:{from_user}-to_user:{to_user}: ' + str(e)}

############################################
# send message to device
############################################
def send_message_to_device(fuser, tuser, title, body, message_type='message', message_class='page', **kwargs):
    res = {'return': True, 'telegram_sent': False, 'email_sent': False, 'sms_sent': False}

    try:
        if tuser.telegram_id:
                from_user = fuser.telegram_id
                from_user_id = fuser.id
                to_user = tuser.telegram_id
                to_user_id = tuser.id
                message_device ='telegram'
                r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs['telegram_body'],  message_type, message_class, message_device, is_html=False)
                if r['return']:
                    res['telegram_sent'] = True

        if tuser.email:
            from_user = fuser.email
            from_user_id = fuser.id
            to_user = tuser.email
            to_user_id = tuser.id
            message_device ='email'
            r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs['email_body'], message_type, message_class, message_device, is_html=True)
            if r['return']:
                res['email_sent'] = True

        if tuser.phonenumber:
            from_user = fuser.phonenumber
            from_user_id = fuser.id
            to_user = tuser.phonenumber
            to_user_id = tuser.id
            message_device ='sms'
            # r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs[sms_body], message_type, message_class, message_device)
            # if r['return']:
            #     res['sms_sent'] = True

        return res
    except Exception as e:
        print(e)
        return {'return': False, 'error': 'error sending message to device: ' + str(e)}
    

############################################
def send_message_to_unknown_user_device(fuser, to_user_email, to_user_phonenumber, to_user_telegram_id, title, body=None, message_type='message', message_class='page', **kwargs):
    res = {'return': True, 'telegram_sent': False, 'email_sent': False, 'sms_sent': False}

    try:
        if to_user_telegram_id:
                from_user = fuser.telegram_id
                from_user_id = fuser.id
                to_user = to_user_telegram_id
                to_user_id = 0
                message_device ='telegram'
                r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs['telegram_body'],  message_type, message_class, message_device, is_html=False)
                if r['return']:
                    res['telegram_sent'] = True

        if to_user_email:
            from_user = fuser.email
            from_user_id = fuser.id
            to_user = to_user_email
            to_user_id = 0
            message_device ='email'
            r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs['email_body'], message_type, message_class, message_device, is_html=True)
            if r['return']:
                res['email_sent'] = True

        if to_user_phonenumber:
            from_user = fuser.phonenumber
            from_user_id = fuser.id
            to_user = to_user_phonenumber
            to_user_id = 0
            message_device ='sms'
            # r = send_message_to_server(from_user, from_user_id, to_user, to_user_id, title, kwargs[sms_body], message_type, message_class, message_device)
            # if r['return']:
            #     res['sms_sent'] = True

        return res
    except Exception as e:
        print(e)
        return {'return': False, 'error': 'error sending message to device: ' + str(e)}
    