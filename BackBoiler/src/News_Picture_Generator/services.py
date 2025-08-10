from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.utils import timezone
from django.http import FileResponse, Http404
import os
import json


BASE_EXTERNAL_PATH = '/home/anews/PS/gan'

json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')

# app_dir = os.path.dirname(os.path.abspath(__file__))
# json_path = os.path.join(app_dir, 'generated_history.json')
# images_dir = os.path.join(os.path.dirname(app_dir), 'News_Picture_Generator', 'crypto_news_images')

# Your existing function stays exactly the same
with open(json_path, 'r', encoding='utf-8') as f:
    data_dict = json.load(f)

@extend_schema(
    description='Download image by news title',
    summary='Download image file matching the given title',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'Exact title of the news item',
                    'example': 'Altseason Brewing, as Bitcoin Dominance Mirrors 2021 Crash?'
                },
            },
            'required': ['title'],
        }
    },
    responses={
        200: OpenApiResponse(description='Image file response'),
        400: OpenApiResponse(description='Bad request - missing title'),
        404: OpenApiResponse(description='Not found - no image for title'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def download_image_by_title(request):
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': "Missing 'title' parameter"}, status=400)
    
    # Reload the JSON file to get latest data
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    # Search for the news item by exact case-insensitive match
    item = None
    for entry in data_dict.values():
        if entry['title'].lower() == title.lower():
            item = entry
            break
    
    if not item:
        return Response({'error': "Image with the given title not found"}, status=404)
    
    filename = os.path.basename(item['filepath'])
    image_path = os.path.join(images_dir, filename)
    
    if not os.path.exists(image_path):
        return Response({'error': "Image file not found on server"}, status=404)
    
    # Return image as FileResponse for download
    response = FileResponse(open(image_path, 'rb'), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# Add this new endpoint to check if an image exists
@extend_schema(
    description='Check if image exists for given title',
    summary='Check if an image has been generated for a title',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'Title to check',
                    'example': 'Bitcoin Reaches New All-Time High'
                },
            },
            'required': ['title'],
        }
    },
    responses={
        200: OpenApiResponse(
            description='Check result',
            response={
                'type': 'object',
                'properties': {
                    'exists': {'type': 'boolean'},
                    'metadata': {'type': 'object', 'nullable': True}
                }
            }
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def check_image_exists(request):
    """Check if image exists for given title"""
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': "Missing 'title' parameter"}, status=400)
    
    # Reload the JSON file to get latest data
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    # Search for the title
    item = None
    for entry in data_dict.values():
        if entry['title'].lower() == title.lower():
            item = entry
            break
    
    if item:
        return Response({
            'exists': True,
            'metadata': {
                'prompt': item.get('prompt'),
                'negative_prompt': item.get('negative_prompt'),
                'tags': item.get('tags', []),
                'cluster': item.get('cluster'),
                'generated_at': item.get('generated_at'),
                'filename': os.path.basename(item.get('filepath', ''))
            }
        })
    
    return Response({
        'exists': False,
        'metadata': None,
        'message': 'Image will be generated in the next cycle (every 30 minutes)'
    })


# Add this endpoint to list all available images
@extend_schema(
    description='List all generated images',
    summary='Get list of all generated images with metadata',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='List of generated images',
            response={
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'images': {
                        'type': 'array',
                        'items': {'type': 'object'}
                    }
                }
            }
        ),
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_generated_images(request):
    """List all generated images"""
    # Reload the JSON file to get latest data
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    images = []
    for entry in data_dict.values():
        images.append({
            'title': entry.get('title'),
            'tags': entry.get('tags', []),
            'cluster': entry.get('cluster'),
            'generated_at': entry.get('generated_at'),
            'filename': os.path.basename(entry.get('filepath', ''))
        })
    
    # Sort by generation time (newest first)
    images.sort(key=lambda x: x.get('generated_at', ''), reverse=True)
    
    return Response({
        'count': len(images),
        'images': images
    })
