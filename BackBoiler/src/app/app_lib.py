
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
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_addresses = [ip.strip() for ip in x_forwarded_for.split(',')]
        for ip in ip_addresses:
            try:
                ipaddress.ip_address(ip)
                return ip
            except ValueError:
                pass
    return request.META.get('REMOTE_ADDR')