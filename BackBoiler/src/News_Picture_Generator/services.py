from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.utils import timezone
from django.http import FileResponse, Http404
import os
import json
import subprocess
import threading
from datetime import datetime



BASE_EXTERNAL_PATH = '/home/anews/PS/gan'

json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')

custom_json_path = os.path.join(BASE_EXTERNAL_PATH, 'custom_pics.json')
custom_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')

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
        filename = os.path.basename(item.get('filepath', ''))
        image_url = request.build_absolute_uri(f'/crypto_news_images/{filename}')
        return Response({
            'exists': True,
            'metadata': {
                'prompt': item.get('prompt'),
                'negative_prompt': item.get('negative_prompt'),
                'tags': item.get('tags', []),
                'cluster': item.get('cluster'),
                'generated_at': item.get('generated_at'),
                'filename': filename,
                'url': image_url
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



@extend_schema(
    description='Get news image generation statistics',
    summary='Get statistics about news image generation',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Generation statistics',
            response={
                'type': 'object',
                'properties': {
                    'total_images': {'type': 'integer'},
                    'total_size_mb': {'type': 'number'},
                    'unique_clusters': {'type': 'array'},
                    'most_common_tags': {'type': 'array'},
                    'generation_by_date': {'type': 'object'},
                    'average_images_per_day': {'type': 'number'}
                }
            }
        ),
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def news_image_stats(request):
    """Get statistics about news image generation"""
    
    # Check if generated_history.json exists
    if not os.path.exists(json_path):
        return Response({
            'total_images': 0,
            'total_size_mb': 0,
            'unique_clusters': [],
            'most_common_tags': [],
            'generation_by_date': {},
            'average_images_per_day': 0,
            'message': 'No news images generated yet'
        })
    
    # Load news images data
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    if not data_dict:
        return Response({
            'total_images': 0,
            'total_size_mb': 0,
            'unique_clusters': [],
            'most_common_tags': [],
            'generation_by_date': {},
            'average_images_per_day': 0
        })
    
    # Calculate statistics
    total_size = 0
    clusters_count = {}
    tags_count = {}
    generation_dates = {}
    earliest_date = None
    latest_date = None
    
    for entry in data_dict.values():
        # Calculate file size
        filename = os.path.basename(entry.get('filepath', ''))
        filepath = os.path.join(images_dir, filename)
        if os.path.exists(filepath):
            total_size += os.path.getsize(filepath)
        
        # Count clusters
        cluster = entry.get('cluster', 'uncategorized')
        clusters_count[cluster] = clusters_count.get(cluster, 0) + 1
        
        # Count tags
        for tag in entry.get('tags', []):
            tags_count[tag] = tags_count.get(tag, 0) + 1
        
        # Count by date
        generated_at = entry.get('generated_at', '')
        if generated_at:
            date_only = generated_at.split(' ')[0]  # Extract date part
            generation_dates[date_only] = generation_dates.get(date_only, 0) + 1
            
            # Track earliest and latest dates
            if not earliest_date or date_only < earliest_date:
                earliest_date = date_only
            if not latest_date or date_only > latest_date:
                latest_date = date_only
    
    # Sort clusters by count
    sorted_clusters = sorted(clusters_count.items(), key=lambda x: x[1], reverse=True)
    unique_clusters = [{'cluster': k, 'count': v} for k, v in sorted_clusters]
    
    # Sort tags by count (top 20)
    sorted_tags = sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:20]
    most_common_tags = [{'tag': k, 'count': v} for k, v in sorted_tags]
    
    # Sort generation dates
    sorted_dates = sorted(generation_dates.items())
    generation_by_date_list = [{'date': k, 'count': v} for k, v in sorted_dates[-30:]]  # Last 30 days
    
    # Calculate average images per day
    avg_per_day = 0
    if earliest_date and latest_date:
        from datetime import datetime
        try:
            start = datetime.strptime(earliest_date, '%Y-%m-%d')
            end = datetime.strptime(latest_date, '%Y-%m-%d')
            days_diff = (end - start).days + 1
            avg_per_day = round(len(data_dict) / days_diff, 2)
        except:
            pass
    
    # Get file format distribution
    format_count = {}
    for entry in data_dict.values():
        filename = os.path.basename(entry.get('filepath', ''))
        ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
        format_count[ext] = format_count.get(ext, 0) + 1
    
    return Response({
        'total_images': len(data_dict),
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2),
        'average_size_mb': round((total_size / len(data_dict)) / (1024 * 1024), 2) if data_dict else 0,
        'unique_clusters': unique_clusters,
        'total_unique_clusters': len(clusters_count),
        'most_common_tags': most_common_tags,
        'total_unique_tags': len(tags_count),
        'generation_by_date': generation_by_date_list,
        'average_images_per_day': avg_per_day,
        'date_range': {
            'earliest': earliest_date,
            'latest': latest_date
        },
        'file_formats': format_count,
        'storage_location': images_dir
    })



# ===== CUSTOM IMAGE GENERATION ENDPOINTS =====

@extend_schema(
    description='Generate custom image with specified parameters',
    summary='Generate a custom image with prompt and dimensions',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'prompt': {
                    'type': 'string',
                    'description': 'Text prompt for image generation',
                    'example': 'A futuristic city with flying cars'
                },
                'width': {
                    'type': 'integer',
                    'description': 'Image width in pixels (64-2048, must be divisible by 8)',
                    'example': 1024
                },
                'height': {
                    'type': 'integer',
                    'description': 'Image height in pixels (64-2048, must be divisible by 8)',
                    'example': 768
                },
                'negative_prompt': {
                    'type': 'string',
                    'description': 'Negative prompt to avoid certain features',
                    'example': 'blurry, low quality',
                    'nullable': True
                },
                'seed': {
                    'type': 'integer',
                    'description': 'Seed for reproducible generation',
                    'example': 42,
                    'nullable': True
                },
                'steps': {
                    'type': 'integer',
                    'description': 'Number of inference steps (default: 20)',
                    'example': 20,
                    'default': 20
                },
                'guidance_scale': {
                    'type': 'number',
                    'description': 'Guidance scale (default: 7.5)',
                    'example': 7.5,
                    'default': 7.5
                }
            },
            'required': ['prompt', 'width', 'height'],
        }
    },
    responses={
        202: OpenApiResponse(
            description='Generation started',
            response={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'message': {'type': 'string'},
                    'generation_id': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Bad request - invalid parameters'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def generate_custom_image(request):
    """Generate a custom image with specified parameters"""
    prompt = request.data.get('prompt', '').strip()
    width = request.data.get('width')
    height = request.data.get('height')
    
    if not prompt:
        return Response({'error': "Missing 'prompt' parameter"}, status=400)
    
    if not width or not height:
        return Response({'error': "Missing 'width' or 'height' parameter"}, status=400)
    
    try:
        width = int(width)
        height = int(height)
    except ValueError:
        return Response({'error': "Width and height must be integers"}, status=400)
    
    # Validate dimensions
    if width < 64 or width > 2048 or height < 64 or height > 2048:
        return Response({'error': "Width and height must be between 64 and 2048"}, status=400)
    
    if width % 8 != 0 or height % 8 != 0:
        return Response({'error': "Width and height must be divisible by 8"}, status=400)
    
    # Get optional parameters
    negative_prompt = request.data.get('negative_prompt', '')
    seed = request.data.get('seed')
    steps = request.data.get('steps', 20)
    guidance_scale = request.data.get('guidance_scale', 7.5)
    
    # Generate unique ID for this generation
    generation_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(prompt) % 10000}"
    
    # Build command
    script_path = os.path.join(os.path.dirname(app_dir), 'News_Picture_Generator', 'custom_image_gen.py')
    cmd = [
        'python', script_path,
        prompt, str(width), str(height),
        '--steps', str(steps),
        '--guidance', str(guidance_scale)
    ]
    
    if negative_prompt:
        cmd.extend(['--negative', negative_prompt])
    
    if seed is not None:
        cmd.extend(['--seed', str(seed)])
    
    # Run generation in background thread
    def run_generation():
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Generation failed: {e}")
    
    thread = threading.Thread(target=run_generation)
    thread.start()
    
    return Response({
        'status': 'started',
        'message': 'Image generation started. Check status or list custom images to see results.',
        'generation_id': generation_id,
        'estimated_time': '30-60 seconds'
    }, status=202)


@extend_schema(
    description='List all custom generated images',
    summary='Get list of all custom generated images with metadata',
    methods=['GET'],
    parameters=[
        {
            'name': 'limit',
            'in': 'query',
            'description': 'Limit number of results',
            'required': False,
            'schema': {'type': 'integer', 'example': 10}
        }
    ],
    responses={
        200: OpenApiResponse(
            description='List of custom generated images',
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
def list_custom_images(request):
    """List all custom generated images"""
    limit = request.GET.get('limit')
    
    # Check if custom_pics.json exists
    if not os.path.exists(custom_json_path):
        return Response({
            'count': 0,
            'images': [],
            'message': 'No custom images generated yet'
        })
    
    # Load custom images data
    with open(custom_json_path, 'r', encoding='utf-8') as f:
        custom_data = json.load(f)
    
    generations = custom_data.get('generations', [])
    
    # Sort by timestamp (newest first)
    generations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Apply limit if specified
    if limit:
        try:
            limit = int(limit)
            generations = generations[:limit]
        except ValueError:
            pass
    
    # Format response
    images = []
    for gen in generations:
        images.append({
            'filename': gen.get('filename'),
            'prompt': gen.get('prompt'),
            'negative_prompt': gen.get('negative_prompt'),
            'width': gen.get('width'),
            'height': gen.get('height'),
            'seed': gen.get('seed'),
            'steps': gen.get('steps'),
            'guidance_scale': gen.get('guidance_scale'),
            'generated_at': gen.get('generated_at')
        })
    
    return Response({
        'count': len(custom_data.get('generations', [])),
        'displayed': len(images),
        'images': images
    })


@extend_schema(
    description='Download custom generated image',
    summary='Download a custom generated image by filename',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'filename': {
                    'type': 'string',
                    'description': 'Filename of the custom image',
                    'example': '20240115_143022_a1b2c3d4_1024x768.png'
                },
            },
            'required': ['filename'],
        }
    },
    responses={
        200: OpenApiResponse(description='Image file response'),
        400: OpenApiResponse(description='Bad request - missing filename'),
        404: OpenApiResponse(description='Not found - image not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def download_custom_image(request):
    """Download a custom generated image"""
    filename = request.data.get('filename', '').strip()
    
    if not filename:
        return Response({'error': "Missing 'filename' parameter"}, status=400)
    
    # Ensure custom images directory exists
    if not os.path.exists(custom_images_dir):
        os.makedirs(custom_images_dir, exist_ok=True)
    
    image_path = os.path.join(custom_images_dir, filename)
    
    if not os.path.exists(image_path):
        return Response({'error': "Image file not found"}, status=404)
    
    # Return image as FileResponse for download
    response = FileResponse(open(image_path, 'rb'), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@extend_schema(
    description='Search custom images by prompt',
    summary='Search custom generated images by prompt text',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'search_text': {
                    'type': 'string',
                    'description': 'Text to search in prompts',
                    'example': 'sunset'
                },
                'include_negative': {
                    'type': 'boolean',
                    'description': 'Also search in negative prompts',
                    'default': False
                }
            },
            'required': ['search_text'],
        }
    },
    responses={
        200: OpenApiResponse(
            description='Search results',
            response={
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'results': {
                        'type': 'array',
                        'items': {'type': 'object'}
                    }
                }
            }
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def search_custom_images(request):
    """Search custom images by prompt text"""
    search_text = request.data.get('search_text', '').strip().lower()
    include_negative = request.data.get('include_negative', False)
    
    if not search_text:
        return Response({'error': "Missing 'search_text' parameter"}, status=400)
    
    # Check if custom_pics.json exists
    if not os.path.exists(custom_json_path):
        return Response({
            'count': 0,
            'results': [],
            'message': 'No custom images to search'
        })
    
    # Load custom images data
    with open(custom_json_path, 'r', encoding='utf-8') as f:
        custom_data = json.load(f)
    
    results = []
    for gen in custom_data.get('generations', []):
        # Search in prompt
        if search_text in gen.get('prompt', '').lower():
            results.append(gen)
        # Search in negative prompt if requested
        elif include_negative and search_text in gen.get('negative_prompt', '').lower():
            results.append(gen)
    
    # Sort by timestamp (newest first)
    results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Format response
    formatted_results = []
    for gen in results:
        
        filename = os.path.basename(gen.get('filepath', ''))
        image_url = request.build_absolute_uri(f'/custom_images/{filename}')
   
        formatted_results.append({
            'filename': gen.get('filename'),
            'prompt': gen.get('prompt'),
            'negative_prompt': gen.get('negative_prompt'),
            'width': gen.get('width'),
            'height': gen.get('height'),
            'seed': gen.get('seed'),
            'generated_at': gen.get('generated_at'),
            'url' : image_url
        })
    
    return Response({
        'count': len(formatted_results),
        'search_text': search_text,
        'results': formatted_results
    })


@extend_schema(
    description='Get custom image generation statistics',
    summary='Get statistics about custom image generation',
    methods=['GET'],
    responses={
        200: OpenApiResponse(
            description='Generation statistics',
            response={
                'type': 'object',
                'properties': {
                    'total_images': {'type': 'integer'},
                    'total_size_mb': {'type': 'number'},
                    'most_common_dimensions': {'type': 'array'},
                    'average_steps': {'type': 'number'},
                    'average_guidance': {'type': 'number'}
                }
            }
        ),
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def custom_image_stats(request):
    """Get statistics about custom image generation"""
    
    # Check if custom_pics.json exists
    if not os.path.exists(custom_json_path):
        return Response({
            'total_images': 0,
            'total_size_mb': 0,
            'most_common_dimensions': [],
            'average_steps': 0,
            'average_guidance': 0,
            'message': 'No custom images generated yet'
        })
    
    # Load custom images data
    with open(custom_json_path, 'r', encoding='utf-8') as f:
        custom_data = json.load(f)
    
    generations = custom_data.get('generations', [])
    
    if not generations:
        return Response({
            'total_images': 0,
            'total_size_mb': 0,
            'most_common_dimensions': [],
            'average_steps': 0,
            'average_guidance': 0
        })
    
    # Calculate statistics
    total_size = 0
    dimensions_count = {}
    total_steps = 0
    total_guidance = 0
    
    for gen in generations:
        # Calculate file size
        filepath = os.path.join(custom_images_dir, gen.get('filename', ''))
        if os.path.exists(filepath):
            total_size += os.path.getsize(filepath)
        
        # Count dimensions
        dim_key = f"{gen.get('width')}x{gen.get('height')}"
        dimensions_count[dim_key] = dimensions_count.get(dim_key, 0) + 1
        
        # Sum steps and guidance
        total_steps += gen.get('steps', 20)
        total_guidance += gen.get('guidance_scale', 7.5)
    
    # Sort dimensions by count
    sorted_dimensions = sorted(dimensions_count.items(), key=lambda x: x[1], reverse=True)
    most_common_dimensions = [{'dimensions': k, 'count': v} for k, v in sorted_dimensions[:5]]
    
    return Response({
        'total_images': len(generations),
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'most_common_dimensions': most_common_dimensions,
        'average_steps': round(total_steps / len(generations), 1) if generations else 0,
        'average_guidance': round(total_guidance / len(generations), 1) if generations else 0,
        'latest_generation': generations[0].get('generated_at') if generations else None
    })


@extend_schema(
    description='Delete a custom generated image',
    summary='Delete a custom image and its metadata',
    methods=['DELETE'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'filename': {
                    'type': 'string',
                    'description': 'Filename of the image to delete',
                    'example': '20240115_143022_a1b2c3d4_1024x768.png'
                },
            },
            'required': ['filename'],
        }
    },
    responses={
        200: OpenApiResponse(description='Image deleted successfully'),
        400: OpenApiResponse(description='Bad request - missing filename'),
        404: OpenApiResponse(description='Not found - image not found'),
    }
)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_custom_image(request):
    """Delete a custom generated image"""
    filename = request.data.get('filename', '').strip()
    
    if not filename:
        return Response({'error': "Missing 'filename' parameter"}, status=400)
    
    # Check if custom_pics.json exists
    if not os.path.exists(custom_json_path):
        return Response({'error': "No custom images found"}, status=404)
    
    # Load custom images data
    with open(custom_json_path, 'r', encoding='utf-8') as f:
        custom_data = json.load(f)
    
    # Find and remove the entry
    generations = custom_data.get('generations', [])
    found = False
    updated_generations = []
    
    for gen in generations:
        if gen.get('filename') == filename:
            found = True
            # Delete the actual file
            filepath = os.path.join(custom_images_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        else:
            updated_generations.append(gen)
    
    if not found:
        return Response({'error': "Image not found in history"}, status=404)
    
    # Update the JSON file
    custom_data['generations'] = updated_generations
    with open(custom_json_path, 'w', encoding='utf-8') as f:
        json.dump(custom_data, f, indent=2, ensure_ascii=False)
    
    return Response({
        'status': 'success',
        'message': f'Image {filename} deleted successfully'
    })


