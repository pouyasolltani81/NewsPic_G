
import os 
import shutil
import ipaddress


###############################################
def Find_npm_bin():
    npm_bin = shutil.which("npm")
    
    if npm_bin:
        return npm_bin
    else:
        raise EnvironmentError("npm is not installed or not found in the system PATH.")

##############################################   
def generate_password(length=5):
    import string, random
    characters =  string.digits 
    return ''.join(random.choice(characters) for _ in range(length))

##############################################
def CheckEmailValidty(email):
        from django.core.validators import EmailValidator
        from django.core.exceptions import ValidationError

        validator = EmailValidator()

        try:
            validator(email)
            return True
        except ValidationError:
            return False
        
##############################################
def CheckPhonenumberValidty(phonenumber):
        import re

        # Define a regular expression pattern for phone numbers
        # This pattern matches numbers in the format +1234567890 or 1234567890

        pattern = r'^\+?\d{10,15}$'
       
        if re.match(pattern, phonenumber):
            return True
        else:
            return False
############################################
def format_round_price(price, precision):
    import math

    precision = int(precision)
    multiplier = 10 ** precision
    rounded_value = math.ceil(float(price) * multiplier) / multiplier
    formatted_price = f'{rounded_value:,.{precision}f}'.rstrip('0').rstrip('.')
    return formatted_price        
##############################################
def get_client_ip(request):
    """Get client IP address from various headers"""
    # Check headers in order of preference
    headers = [
        'HTTP_CF_CONNECTING_IP',  # Cloudflare
        'HTTP_X_REAL_IP',         # Nginx
        'HTTP_X_FORWARDED_FOR',   # Standard proxy header
        'HTTP_X_FORWARDED',       # Less common
        'HTTP_X_CLUSTER_CLIENT_IP',
        'HTTP_FORWARDED_FOR',
        'HTTP_FORWARDED',
        'REMOTE_ADDR'             # Direct connection
    ]
    
    for header in headers:
        ip = request.META.get(header)
        if ip:
            # Handle comma-separated IPs (proxy chains)
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            # Remove port if present
            if ':' in ip and not ip.count(':') > 1:  # Not IPv6
                ip = ip.split(':')[0]
            # Skip localhost/private IPs if we have better options
            if ip and not ip.startswith(('127.', '10.', '192.168.', '172.')):
                return ip
            elif ip and header == 'REMOTE_ADDR':  # Use as fallback
                return ip
    
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

#################################################


############################################
def get_phonenumber_start_with_zero(phonenumber):
    try:
        if not CheckPhonenumberValidty(phonenumber):
            return None

        # Ensure the phone number starts with '0'
        if phonenumber.startswith('00'):
            phonenumber = phonenumber[2:]
        if phonenumber.startswith('0'):
            phonenumber = phonenumber[1:]
        if phonenumber.startswith('+'):
            phonenumber = phonenumber[1:]
        if phonenumber.startswith('98'):
            phonenumber = phonenumber[2:]
        if phonenumber.startswith('+98'):
            phonenumber = phonenumber[3:]
        
        return '0' + phonenumber
        
    except Exception as e:
        print(f"Error in get_phonenumber_start_with_zero: {e}")
        return None