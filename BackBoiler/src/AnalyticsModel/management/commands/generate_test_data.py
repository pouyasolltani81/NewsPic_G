# AnalyticsModel/management/commands/generate_test_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
from AnalyticsModel.models import APIEndpoint, APIRequest, UserSession , ErrorLog
from django.db import transaction

User = get_user_model()

class Command(BaseCommand):
    help = 'Generate test data for analytics'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Create test users if needed
            users = list(User.objects.all())
            if len(users) < 5:
                self.stdout.write('Creating test users...')
                for i in range(5):
                    user, created = User.objects.get_or_create(
                        username=f'testuser{i}',
                        defaults={
                            'email': f'test{i}@example.com',
                            'is_active': True
                        }
                    )
                    if created:
                        user.set_password('testpass123')
                        user.save()
                users = list(User.objects.all())

            # Create test endpoints
            endpoints_data = [
                ('GET', '/api/users/', 'List users'),
                ('POST', '/api/users/', 'Create user'),
                ('GET', '/api/products/', 'List products'),
                ('GET', '/api/orders/', 'List orders'),
                ('POST', '/api/orders/', 'Create order'),
                ('GET', '/api/dashboard/', 'Dashboard data'),
                ('PUT', '/api/users/{id}/', 'Update user'),
                ('DELETE', '/api/users/{id}/', 'Delete user'),
                ('GET', '/api/stats/', 'Statistics'),
                ('POST', '/api/login/', 'User login'),
            ]

            endpoints = []
            for method, path, desc in endpoints_data:
                endpoint, created = APIEndpoint.objects.get_or_create(
                    method=method,
                    path=path,
                    defaults={'description': desc}
                )
                endpoints.append(endpoint)
                if created:
                    self.stdout.write(f'Created endpoint: {method} {path}')

            # Generate requests for the last 24 hours
            now = timezone.now()
            
            self.stdout.write('Generating API requests...')
            for i in range(500):  
                    # Timestamp
                hours_ago = random.uniform(0, 24)
                timestamp = now - timedelta(hours=hours_ago)

                # Endpoint
                endpoint = random.choice(endpoints)

                # User (can be None)
                user = random.choice(users + [None, None]) if users else None

                # Response time
                response_time = random.gammavariate(2, 20)
                if random.random() < 0.1:
                    response_time *= 10

                # Status code
                status_code = random.choices(
                    [200, 201, 400, 401, 403, 404, 500, 502],
                    weights=[60, 10, 8, 5, 5, 8, 3, 1]
                )[0]

                # Device type
                device_type = random.choices(['desktop', 'mobile', 'tablet'], weights=[60, 35, 5])[0]

                # Browser
                browsers = [
                    ('Chrome', '91.0'),
                    ('Firefox', '89.0'),
                    ('Safari', '14.1'),
                    ('Edge', '91.0'),
                    ('Mobile Safari', '14.0')
                ]
                browser = random.choice(browsers)

                # Operating system
                os_list = ['Windows 10', 'macOS', 'Ubuntu', 'iOS', 'Android']
                os_name = random.choice(os_list)

                # Country / city
                locations = [
                    ('United States', 'New York'),
                    ('United States', 'Los Angeles'),
                    ('United Kingdom', 'London'),
                    ('Germany', 'Berlin'),
                    ('France', 'Paris'),
                    ('Canada', 'Toronto'),
                    ('Australia', 'Sydney'),
                    ('Japan', 'Tokyo'),
                ]
                country, city = random.choice(locations)

                # Create request
                api_request = APIRequest.objects.create(
                    endpoint=endpoint,
                    user=user,
                    timestamp=timestamp,
                    response_time=response_time,
                    status_code=status_code,
                    ip_address=f"192.168.{random.randint(0, 255)}.{random.randint(1, 255)}",
                    user_agent=f"Mozilla/5.0 ({os_name}) {browser[0]}/{browser[1]}",
                    request_body_size=random.randint(0, 1000),
                    response_body_size=random.randint(100, 5000),
                    device_type=device_type,
                    browser=f"{browser[0]} {browser[1]}",
                    os=os_name,
                    country=country,
                    city=city,
                    query_params={'page': random.randint(1, 10)} if random.random() > 0.5 else {},
                    error_message='Test error' if status_code >= 500 else None
                )

                # --- Add dummy ErrorLog for failed requests ---
                if status_code >= 500:
                    ErrorLog.objects.create(
                        user=user,
                        endpoint=endpoint,
                        timestamp=timestamp,
                        error_type='ServerError',
                        error_message='Simulated server error',
                        traceback='Traceback (most recent call last): ... simulated ...',
                        request_data={
                            'method': endpoint.method,
                            'path': endpoint.path,
                            'query_params': {'page': random.randint(1, 10)} if random.random() > 0.5 else {},
                            'headers': {'User-Agent': f"Mozilla/5.0 ({os_name}) {browser[0]}/{browser[1]}"},
                        }
                    )
                # Random time in last 24 hours
                hours_ago = random.uniform(0, 24)
                timestamp = now - timedelta(hours=hours_ago)
                
                # Random endpoint
                endpoint = random.choice(endpoints)
                
                # Random user (or None for anonymous)
                user = random.choice(users + [None, None])  # 40% anonymous
                
                # Random response time (weighted towards faster times)
                response_time = random.gammavariate(2, 20)  # Most requests fast
                if random.random() < 0.1:  # 10% chance of slow request
                    response_time *= 10
                
                # Random status code (weighted towards success)
                status_code = random.choices(
                    [200, 201, 400, 401, 403, 404, 500, 502],
                    weights=[60, 10, 8, 5, 5, 8, 3, 1]
                )[0]
                
                # Device types
                device_type = random.choices(
                    ['desktop', 'mobile', 'tablet'],
                    weights=[60, 35, 5]
                )[0]
                
                # Browsers
                browsers = [
                    ('Chrome', '91.0'),
                    ('Firefox', '89.0'),
                    ('Safari', '14.1'),
                    ('Edge', '91.0'),
                    ('Mobile Safari', '14.0')
                ]
                browser = random.choice(browsers)
                
                # Operating systems
                os_list = ['Windows 10', 'macOS', 'Ubuntu', 'iOS', 'Android']
                os_name = random.choice(os_list)
                
                # Countries and cities
                locations = [
                    ('United States', 'New York'),
                    ('United States', 'Los Angeles'),
                    ('United Kingdom', 'London'),
                    ('Germany', 'Berlin'),
                    ('France', 'Paris'),
                    ('Canada', 'Toronto'),
                    ('Australia', 'Sydney'),
                    ('Japan', 'Tokyo'),
                ]
                country, city = random.choice(locations)
                
                # Create request
                APIRequest.objects.create(
                    endpoint=endpoint,
                    user=user,
                    timestamp=timestamp,
                    response_time=response_time,
                    status_code=status_code,
                    ip_address=f"192.168.{random.randint(0, 255)}.{random.randint(1, 255)}",
                    user_agent=f"Mozilla/5.0 ({os_name}) {browser[0]}/{browser[1]}",
                    request_body_size=random.randint(0, 1000),
                    response_body_size=random.randint(100, 5000),
                    device_type=device_type,
                    browser=f"{browser[0]} {browser[1]}",
                    os=os_name,
                    country=country,
                    city=city,
                    query_params={'page': random.randint(1, 10)} if random.random() > 0.5 else {},
                    error_message='Test error' if status_code >= 500 else None
                )
                
                if i % 100 == 0:
                    self.stdout.write(f'Generated {i} requests...')

            self.stdout.write(self.style.SUCCESS(f'Generated 500 test requests'))

            # Create some active sessions
            self.stdout.write('Creating user sessions...')
            for user in users[:3]:
                # Clean up old sessions for this user
                UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
                # In generate_test_data.py, use real public IPs for testing:
                test_ips = [
                    '8.8.8.8',  # Google DNS - USA
                    '1.1.1.1',  # Cloudflare - USA
                    '134.195.196.1',  # Germany
                    '5.160.139.200',  # Iran
                    '2.144.173.23',  # Iran
                    '103.215.223.11',  # Iran
                ]

                # Use these IPs when creating test requests
                ip_address_test = random.choice(test_ips)
                
                session = UserSession.objects.create(
                    user=user,
                    session_key=f"test_session_{user.id}_{random.randint(1000, 9999)}",
                    # ip_address=f"192.168.1.{random.randint(1, 255)}",
                    ip_address=ip_address_test,
                    
                    user_agent="Mozilla/5.0 Test Browser",
                    is_active=True,
                    page_views=random.randint(5, 50),
                    api_calls=random.randint(10, 100),
                    total_response_time=random.uniform(1000, 5000),
                    last_activity=now - timedelta(minutes=random.randint(0, 30))
                )

            self.stdout.write(self.style.SUCCESS('Test data generated successfully!'))
            
            # Print summary
            self.stdout.write('\nSummary:')
            self.stdout.write(f'Total endpoints: {APIEndpoint.objects.count()}')
            self.stdout.write(f'Total requests: {APIRequest.objects.count()}')
            self.stdout.write(f'Active sessions: {UserSession.objects.filter(is_active=True).count()}')
            self.stdout.write(f'Total users: {User.objects.count()}')