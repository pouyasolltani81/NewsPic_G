
import requests
from LogModel.log_handler import print_log

def asp_request_to_exec(asp, params, headers):
        
    url = asp.url() + '/Connect/RequestToExec/'
    
    try:
        response = requests.post(url, json=params, headers=headers)
        
        return {'return': True,  'response': response.json()}
    except Exception as e:
        print(e)
        print_log(level='error', message='Error asp_request_to_exec', exception_type=e.__class__.__name__, stack_trace=str(e), file_path=__file__, line_number=0, view_name='asp_request_to_exec')
        return {'return': False, 'error': 'Error asp_request_to_exec : ' + str(e)}
##################################################################
def asp_service_register_by_email(asp, email_, pass_):
    # when we register user by email then want to register by email in other asps
    params = {
        'asp_uuid': str(asp.app_uuid),
        'route': '/User/ServiceRegister/',
        'method': 'POST',
        'params': {
            'email': email_,
            'password': pass_,
        },
        'headers': {
            'Authorization': asp.app_token,
            'Content-Type': 'application/json'
        }
    }
    
    headers = {
        'Authorization': asp.app_token,
        'Content-Type': 'application/json'
    }
    try:
        res = asp_request_to_exec(asp, params, headers)
        
        return {'return': True,  'response': res}
    except Exception as e:
        print(e)
        print_log(level='error', message='Error asp_service_register_by_email', exception_type=e.__class__.__name__, stack_trace=str(e), file_path=__file__, line_number=0, view_name='asp_service_register')
        return {'return': False, 'error': 'Error asp_service_register_by_email : ' + str(e)}            