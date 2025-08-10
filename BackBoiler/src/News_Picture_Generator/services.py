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
                    'description': 'Guidance scale (default: 4.5)',
                    'example': 4.5,
                    'default': 4.5
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
    
    # Build command - FIX: Define app_dir properly
    current_dir = BASE_EXTERNAL_PATH
    script_path = os.path.join(BASE_EXTERNAL_PATH, 'custom_image_gen.py')
    
    # Check if script exists
    if not os.path.exists(script_path):
        return Response({
            'error': f"Generation script not found at {script_path}",
            'hint': "Make sure custom_image_gen.py is in the News_Picture_Generator directory"
        }, status=500)
    
    # Build command with proper argument handling
    import sys
    cmd = [
        sys.executable,  # Use the same Python interpreter as Django
        script_path,
        prompt,  # This will be properly quoted by subprocess
        str(width),
        str(height),
        '--steps', str(steps),
        '--guidance', str(guidance_scale)
    ]
    
    if negative_prompt:
        cmd.extend(['--negative', negative_prompt])
    
    if seed is not None:
        cmd.extend(['--seed', str(seed)])
    
    # Add output and history paths
    cmd.extend([
        '--output', custom_images_dir,
        '--history', custom_json_path
    ])
    
    # Ensure custom images directory exists
    if not os.path.exists(custom_images_dir):
        os.makedirs(custom_images_dir, exist_ok=True)
    
    # Run generation in background thread
    def run_generation():
        try:
            # Use subprocess.run with proper argument handling
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                cwd=current_dir  # Set working directory
            )
            print(f"Generation completed successfully")
            if result.stdout:
                print(f"Output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"Generation failed with exit code {e.returncode}")
            print(f"Error output: {e.stderr}")
            print(f"Standard output: {e.stdout}")
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
    
    thread = threading.Thread(target=run_generation)
    thread.daemon = True  # Make thread daemon so it doesn't block server shutdown
    thread.start()
    
    return Response({
        'status': 'started',
        'message': 'Image generation started. Check status or list custom images to see results.',
        'generation_id': generation_id,
        'estimated_time': '30-60 seconds',
        'prompt': prompt,
        'dimensions': f"{width}x{height}"
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

@api_view(['POST'])
@permission_classes([IsAdminUser])
def search_custom_images(request):
    """Search custom images by prompt text or generation ID"""
    search_text = request.data.get('search_text', '').strip().lower()
    generation_id = request.data.get('generation_id', '').strip()
    include_negative = request.data.get('include_negative', False)
    
    if not search_text and not generation_id:
        return Response({'error': "Must provide either 'search_text' or 'generation_id'"}, status=400)
    
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
    
    if generation_id:
        # Search by generation_id
        # Extract the timestamp part from generation_id (before the underscore)
        gen_id_parts = generation_id.split('_')
        if gen_id_parts:
            gen_timestamp = gen_id_parts[0]  # This is "20250810144624"
            
            # Convert to the format used in filename: YYYYMMDD_HHMMSS
            if len(gen_timestamp) == 14:  # Format: YYYYMMDDHHMMSS
                gen_date = gen_timestamp[:8]  # 20250810
                gen_time = gen_timestamp[8:]  # 144624
                
                for gen in custom_data.get('generations', []):
                    filename = gen.get('filename', '')
                    
                    # Check if the filename starts with the same date and has similar time
                    # The filename format is: YYYYMMDD_HHMMSS_hash_dimensions.png
                    if filename.startswith(gen_date):
                        # Extract time from filename
                        filename_parts = filename.split('_')
                        if len(filename_parts) >= 2:
                            file_time = filename_parts[1]  # This is "144643"
                            
                            # Check if times are close (within a minute or so)
                            # Or check if this entry was created around the same time
                            if abs(int(file_time) - int(gen_time)) < 100:  # Within 1 minute
                                results.append(gen)
                                break
                    
                    # Also check timestamp field if it exists
                    if gen.get('timestamp'):
                        # Parse ISO timestamp and compare
                        import datetime
                        try:
                            entry_time = datetime.datetime.fromisoformat(gen['timestamp'].replace('Z', '+00:00'))
                            gen_datetime = datetime.datetime.strptime(gen_timestamp, '%Y%m%d%H%M%S')
                            
                            # If within 1 minute
                            if abs((entry_time - gen_datetime).total_seconds()) < 60:
                                results.append(gen)
                                break
                        except:
                            pass
    else:
        # Search by text (keep existing logic)
        for gen in custom_data.get('generations', []):
            if search_text in gen.get('prompt', '').lower():
                results.append(gen)
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
            'generation_id': generation_id if generation_id else None,
            'prompt': gen.get('prompt'),
            'negative_prompt': gen.get('negative_prompt'),
            'width': gen.get('width'),
            'height': gen.get('height'),
            'seed': gen.get('seed'),
            'generated_at': gen.get('generated_at'),
            'url': image_url
        })
    
    return Response({
        'count': len(formatted_results),
        'search_criteria': {
            'text': search_text if search_text else None,
            'generation_id': generation_id if generation_id else None
        },
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




# ===== CUSTOM LOGO  ENDPOINTS =====
from PIL import Image, ImageDraw, ImageFont, ImageStat
import io
from django.conf import settings
import numpy as np

@extend_schema(
    description='Download news image with adaptive vertical logo overlay',
    summary='Download news image with a vertical logo that adapts to background brightness',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'Exact title of the news item',
                    'example': 'Bitcoin Reaches New All-Time High'
                },
                'light_logo_path': {
                    'type': 'string',
                    'description': 'Path to light mode logo (for dark backgrounds)',
                    'example': '/home/anews/PS/gan/my_concept/logo_light.png',
                    'nullable': True
                },
                'dark_logo_path': {
                    'type': 'string',
                    'description': 'Path to dark mode logo (for light backgrounds)',
                    'example': '/home/anews/PS/gan/my_concept/logo_dark.png',
                    'nullable': True
                },
                'strip_width_percentage': {
                    'type': 'integer',
                    'description': 'Width of the vertical strip as percentage of image width (3-15)',
                    'example': 8,
                    'default': 8
                },
                'logo_opacity': {
                    'type': 'number',
                    'description': 'Logo and text opacity (0.0-1.0)',
                    'example': 0.9,
                    'default': 0.9
                },
                'strip_opacity': {
                    'type': 'number',
                    'description': 'Strip background opacity (0.0-1.0)',
                    'example': 0.7,
                    'default': 0.7
                },
                'font_size_percentage': {
                    'type': 'integer',
                    'description': 'Font size as percentage of strip width (40-80)',
                    'example': 60,
                    'default': 60
                },
                'brightness_threshold': {
                    'type': 'integer',
                    'description': 'Brightness threshold (0-255) to determine dark/light background',
                    'example': 128,
                    'default': 128
                },
                'output_format': {
                    'type': 'string',
                    'description': 'Output format (png or jpg)',
                    'example': 'png',
                    'default': 'png',
                    'enum': ['png', 'jpg']
                },
                'output_quality': {
                    'type': 'integer',
                    'description': 'Output quality for JPG (1-100)',
                    'example': 95,
                    'default': 95
                }
            },
            'required': ['title'],
        }
    },
    responses={
        200: OpenApiResponse(description='Image file with adaptive vertical logo overlay'),
        400: OpenApiResponse(description='Bad request - invalid parameters'),
        404: OpenApiResponse(description='Not found - image or logo not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def download_image_with_logo(request):
    """Download news image with adaptive vertical logo overlay"""
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': "Missing 'title' parameter"}, status=400)
    
    # Get parameters
    light_logo_path = request.data.get('light_logo_path')
    dark_logo_path = request.data.get('dark_logo_path')
    strip_width_percentage = request.data.get('strip_width_percentage', 8)
    logo_opacity = request.data.get('logo_opacity', 0.9)
    strip_opacity = request.data.get('strip_opacity', 0.7)
    font_size_percentage = request.data.get('font_size_percentage', 60)
    brightness_threshold = request.data.get('brightness_threshold', 128)
    output_format = request.data.get('output_format', 'png').lower()
    output_quality = request.data.get('output_quality', 95)
    
    # Validate parameters
    try:
        strip_width_percentage = int(strip_width_percentage)
        if not 3 <= strip_width_percentage <= 15:
            return Response({'error': "strip_width_percentage must be between 3 and 15"}, status=400)
    except ValueError:
        return Response({'error': "strip_width_percentage must be an integer"}, status=400)
    
    try:
        logo_opacity = float(logo_opacity)
        strip_opacity = float(strip_opacity)
        if not 0.0 <= logo_opacity <= 1.0 or not 0.0 <= strip_opacity <= 1.0:
            return Response({'error': "opacity values must be between 0.0 and 1.0"}, status=400)
    except ValueError:
        return Response({'error': "opacity must be a number"}, status=400)
    
    try:
        font_size_percentage = int(font_size_percentage)
        if not 40 <= font_size_percentage <= 80:
            return Response({'error': "font_size_percentage must be between 40 and 80"}, status=400)
    except ValueError:
        return Response({'error': "font_size_percentage must be an integer"}, status=400)
    
    try:
        brightness_threshold = int(brightness_threshold)
        if not 0 <= brightness_threshold <= 255:
            return Response({'error': "brightness_threshold must be between 0 and 255"}, status=400)
    except ValueError:
        return Response({'error': "brightness_threshold must be an integer"}, status=400)
    
    if output_format not in ['png', 'jpg']:
        return Response({'error': "output_format must be 'png' or 'jpg'"}, status=400)
    
    try:
        output_quality = int(output_quality)
        if not 1 <= output_quality <= 100:
            return Response({'error': "output_quality must be between 1 and 100"}, status=400)
    except ValueError:
        return Response({'error': "output_quality must be an integer"}, status=400)
    
    # Reload the JSON file to get latest data
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    # Search for the news item
    item = None
    for entry in data_dict.values():
        if entry['title'].lower() == title.lower():
            item = entry
            break
    
    if not item:
        return Response({'error': "Image with the given title not found"}, status=404)
    
    # Get the original image
    filename = os.path.basename(item['filepath'])
    image_path = os.path.join(images_dir, filename)
    
    if not os.path.exists(image_path):
        return Response({'error': "Image file not found on server"}, status=404)
    
    # Set default logo paths if not provided
    if not light_logo_path or not dark_logo_path:
        # Try to find default logos
        possible_light_paths = [
            '/home/anews/PS/gan/my_concept/logo_light.png',
            os.path.join(settings.STATIC_ROOT, 'images', 'logo_light.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_light.png'),
        ]
        
        possible_dark_paths = [
            '/home/anews/PS/gan/my_concept/logo_dark.png',
            os.path.join(settings.STATIC_ROOT, 'images', 'logo_dark.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_dark.png'),
        ]
        
        if not light_logo_path:
            for path in possible_light_paths:
                if os.path.exists(path):
                    light_logo_path = path
                    break
        
        if not dark_logo_path:
            for path in possible_dark_paths:
                if os.path.exists(path):
                    dark_logo_path = path
                    break
        
        if not light_logo_path or not dark_logo_path:
            # If only one logo is found, use it for both
            if light_logo_path and not dark_logo_path:
                dark_logo_path = light_logo_path
            elif dark_logo_path and not light_logo_path:
                light_logo_path = dark_logo_path
            else:
                return Response({
                    'error': "No logo files found. Please provide both light_logo_path and dark_logo_path"
                }, status=404)
    
    # Validate logo paths
    if not os.path.exists(light_logo_path):
        return Response({'error': f"Light logo file not found at: {light_logo_path}"}, status=404)
    if not os.path.exists(dark_logo_path):
        return Response({'error': f"Dark logo file not found at: {dark_logo_path}"}, status=404)
    
    try:
        # Open the main image
        main_image = Image.open(image_path).convert('RGBA')
        main_width, main_height = main_image.size
        
        # Calculate strip width
        strip_width = int(main_width * (strip_width_percentage / 100))
        
        # Analyze the brightness of the left edge where the strip will be
        left_edge = main_image.crop((0, 0, strip_width, main_height))
        
        # Convert to grayscale for brightness analysis
        gray_edge = left_edge.convert('L')
        
        # Calculate average brightness
        stat = ImageStat.Stat(gray_edge)
        avg_brightness = stat.mean[0]
        
        # Determine if background is dark or light
        is_dark_background = avg_brightness < brightness_threshold
        
        # Select appropriate logo and colors
        if is_dark_background:
            # Dark background: use light logo and white text
            logo_path = light_logo_path
            text_color = '#FFFFFF'
            strip_color = '#000000'  # Black strip for contrast
        else:
            # Light background: use dark logo and dark text
            logo_path = dark_logo_path
            text_color = '#1F1E2E'
            strip_color = '#FFFFFF'  # White strip for contrast
        
        # Create a copy of the main image
        output_image = main_image.copy()
        
        # Create a semi-transparent strip overlay
        strip = Image.new('RGBA', (strip_width, main_height), (0, 0, 0, 0))
        strip_draw = ImageDraw.Draw(strip)
        
        # Parse strip color
        if strip_color.startswith('#'):
            r = int(strip_color[1:3], 16)
            g = int(strip_color[3:5], 16)
            b = int(strip_color[5:7], 16)
        else:
            r, g, b = 0, 0, 0
        
        # Draw semi-transparent background
        # strip_draw.rectangle(
        #     [(0, 0), (strip_width, main_height)],
        #     fill=(r, g, b, int(255 * strip_opacity))
        # )
        
        # Open and resize logo
        logo = Image.open(logo_path).convert('RGBA')
        logo_size = int(strip_width * 0.3)  # Small - 30% of strip width
        logo_aspect = logo.height / logo.width
        logo_height = int(logo_size * logo_aspect)

        # Ensure logo fits in the strip
        if logo_height > logo_size:
            logo_height = logo_size
            logo_size = int(logo_height / logo_aspect)

        logo = logo.resize((logo_size, logo_height), Image.Resampling.LANCZOS)

        # Rotate logo 90 degrees to the right
        logo = logo.rotate(-90, expand=True)
        # Swap dimensions after rotation
        logo_size, logo_height = logo_height, logo_size

        # Apply opacity to logo
        if logo_opacity < 1.0:
            logo_with_opacity = Image.new('RGBA', logo.size, (0, 0, 0, 0))
            logo_with_opacity.paste(logo, (0, 0))
            logo_array = logo_with_opacity.split()
            if len(logo_array) == 4:
                alpha = logo_array[3]
                alpha = alpha.point(lambda p: p * logo_opacity)
                logo_with_opacity.putalpha(alpha)
                logo = logo_with_opacity

        # Increase top padding
        top_padding = 50  # Increased from 20

        # Position logo at the top with more padding
        logo_x = (strip_width - logo_size) // 2  # Center horizontally
        logo_y = top_padding
        strip.paste(logo, (logo_x, logo_y), logo)

        # Add "Aimoonhub" text vertically, RIGHT BELOW the logo with NO gap
        text = "Aimoonhub"

        # Load font (keep existing font loading code)
        font_size = int(strip_width * (font_size_percentage / 200))
        try:
            font_paths = [
                '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                'C:\\Windows\\Fonts\\Arial.ttf',
            ]
            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    break
            if not font:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Create a temporary image for vertical text
        text_img = Image.new('RGBA', (main_height, strip_width), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Calculate text dimensions
        text_bbox = text_draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Position text RIGHT AFTER the logo ends (no gap)
        text_start_y = logo_y + logo_height + 10 # Start immediately after logo
        available_height = main_height - text_start_y - 20

        if text_width <= available_height:
            # Position text starting right after logo
            text_x = text_start_y  # Start where logo ends
            text_y = (strip_width - text_height) // 2  # Center horizontally in strip
            
            # Parse text color
            if text_color.startswith('#'):
                tr = int(text_color[1:3], 16)
                tg = int(text_color[3:5], 16)
                tb = int(text_color[5:7], 16)
            else:
                tr, tg, tb = 255, 255, 255
            
            # Draw text
            text_draw.text(
                (text_x, text_y),
                text,
                fill=(tr, tg, tb, int(255 * logo_opacity)),
                font=font
            )
            
            # Rotate text image 90 degrees clockwise
            text_img = text_img.rotate(-90, expand=True)
            
            # Paste rotated text onto strip
            strip.paste(text_img, (0, 0), text_img)

        # Paste the strip onto the main image
        output_image.paste(strip, (0, 0), strip)
        
        # Convert to RGB if saving as JPG
        if output_format == 'jpg':
            rgb_image = Image.new('RGB', output_image.size, (255, 255, 255))
            rgb_image.paste(output_image, mask=output_image.split()[3] if len(output_image.split()) == 4 else None)
            output_image = rgb_image
        
        # Save to BytesIO
        img_io = io.BytesIO()
        save_kwargs = {'format': output_format.upper()}
        if output_format == 'jpg':
            save_kwargs['quality'] = output_quality
            save_kwargs['optimize'] = True
        
        output_image.save(img_io, **save_kwargs)
        img_io.seek(0)
        
        # Prepare response
        content_type = f'image/{output_format}'
        original_name = os.path.splitext(filename)[0]
        new_filename = f"{original_name}_with_adaptive_logo.{output_format}"
        
        response = FileResponse(img_io, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{new_filename}"'
        
        # Add metadata headers
        response['X-Strip-Width'] = str(strip_width)
        response['X-Logo-Size'] = f"{logo_size}x{logo_height}"
        response['X-Original-Size'] = f"{main_width}x{main_height}"
        response['X-Background-Type'] = 'dark' if is_dark_background else 'light'
        response['X-Average-Brightness'] = str(round(avg_brightness, 2))
        response['X-Logo-Used'] = 'light' if is_dark_background else 'dark'
        response['X-Text-Color'] = text_color
        
        return response
        
    except Exception as e:
        return Response({
            'error': f"Failed to process image: {str(e)}",
            'type': type(e).__name__
        }, status=500)


@extend_schema(
    description='Analyze image brightness and preview adaptive logo settings',
    summary='Check which logo and colors will be used based on image brightness',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'Exact title of the news item',
                    'example': 'Bitcoin Reaches New All-Time High'
                },
                'strip_width_percentage': {
                    'type': 'integer',
                    'description': 'Width of the vertical strip as percentage of image width (3-15)',
                    'example': 8,
                    'default': 8
                },
                'brightness_threshold': {
                    'type': 'integer',
                    'description': 'Brightness threshold (0-255) to determine dark/light background',
                    'example': 128,
                    'default': 128
                }
            },
            'required': ['title'],
        }
    },
    responses={
        200: OpenApiResponse(
            description='Brightness analysis results',
            response={
                'type': 'object',
                'properties': {
                    'average_brightness': {'type': 'number'},
                    'is_dark_background': {'type': 'boolean'},
                    'recommended_logo': {'type': 'string'},
                    'recommended_text_color': {'type': 'string'},
                    'brightness_map': {'type': 'object'}
                }
            }
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def analyze_image_brightness(request):
    """Analyze image brightness for adaptive logo placement"""
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': "Missing 'title' parameter"}, status=400)
    
    strip_width_percentage = request.data.get('strip_width_percentage', 8)
    brightness_threshold = request.data.get('brightness_threshold', 128)
    
    # Validate parameters
    try:
        strip_width_percentage = int(strip_width_percentage)
        if not 3 <= strip_width_percentage <= 15:
            return Response({'error': "strip_width_percentage must be between 3 and 15"}, status=400)
    except ValueError:
        return Response({'error': "strip_width_percentage must be an integer"}, status=400)
    
    try:
        brightness_threshold = int(brightness_threshold)
        if not 0 <= brightness_threshold <= 255:
            return Response({'error': "brightness_threshold must be between 0 and 255"}, status=400)
    except ValueError:
        return Response({'error': "brightness_threshold must be an integer"}, status=400)
    
    # Find the image
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    item = None
    for entry in data_dict.values():
        if entry['title'].lower() == title.lower():
            item = entry
            break
    
    if not item:
        return Response({'error': "Image with the given title not found"}, status=404)
    
    # Get image path
    filename = os.path.basename(item['filepath'])
    image_path = os.path.join(images_dir, filename)
    
    if not os.path.exists(image_path):
        return Response({'error': "Image file not found on server"}, status=404)
    
    try:
        # Open the image
        image = Image.open(image_path).convert('RGBA')
        width, height = image.size
        
        # Calculate strip width
        strip_width = int(width * (strip_width_percentage / 100))
        
        # Analyze the left edge
        left_edge = image.crop((0, 0, strip_width, height))
        gray_edge = left_edge.convert('L')
        
        # Get brightness statistics
        stat = ImageStat.Stat(gray_edge)
        avg_brightness = stat.mean[0]
        min_brightness = stat.extrema[0][0]
        max_brightness = stat.extrema[0][1]
        
        # Determine if background is dark or light
        is_dark_background = avg_brightness < brightness_threshold
        
        # Analyze brightness in sections (top, middle, bottom)
        section_height = height // 3
        sections = {
            'top': gray_edge.crop((0, 0, strip_width, section_height)),
            'middle': gray_edge.crop((0, section_height, strip_width, 2 * section_height)),
            'bottom': gray_edge.crop((0, 2 * section_height, strip_width, height))
        }
        
        brightness_map = {}
        for name, section in sections.items():
            section_stat = ImageStat.Stat(section)
            brightness_map[name] = {
                'average': round(section_stat.mean[0], 2),
                'min': section_stat.extrema[0][0],
                'max': section_stat.extrema[0][1]
            }
        
        return Response({
            'average_brightness': round(avg_brightness, 2),
            'min_brightness': min_brightness,
            'max_brightness': max_brightness,
            'brightness_threshold': brightness_threshold,
            'is_dark_background': is_dark_background,
            'recommended_logo': 'light' if is_dark_background else 'dark',
            'recommended_text_color': '#FFFFFF' if is_dark_background else '#1F1E2E',
            'recommended_strip_color': '#000000' if is_dark_background else '#FFFFFF',
            'strip_width_pixels': strip_width,
            'brightness_map': brightness_map,
            'filename': filename,
            'image_size': {'width': width, 'height': height}
        })
        
    except Exception as e:
        return Response({
            'error': f"Failed to analyze image: {str(e)}"
        }, status=500)





@extend_schema(
    description='Preview news image with logo overlay',
    summary='Preview how the logo will look on the image without downloading',
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'Exact title of the news item',
                    'example': 'Bitcoin Reaches New All-Time High'
                },
                'logo_size_percentage': {
                    'type': 'integer',
                    'description': 'Logo size as percentage of image width (5-30)',
                    'example': 15,
                    'default': 15
                },
                'logo_padding': {
                    'type': 'integer',
                    'description': 'Padding from edges in pixels',
                    'example': 20,
                    'default': 20
                }
            },
            'required': ['title'],
        }
    },
    responses={
        200: OpenApiResponse(
            description='Preview information',
            response={
                'type': 'object',
                'properties': {
                    'original_size': {'type': 'object'},
                    'logo_size': {'type': 'object'},
                    'logo_position': {'type': 'object'},
                    'preview_url': {'type': 'string', 'nullable': True}
                }
            }
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_logo_placement(request):
    """Preview logo placement on image"""
    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': "Missing 'title' parameter"}, status=400)
    
    logo_size_percentage = request.data.get('logo_size_percentage', 15)
    logo_padding = request.data.get('logo_padding', 20)
    
    # Validate parameters
    try:
        logo_size_percentage = int(logo_size_percentage)
        if not 5 <= logo_size_percentage <= 30:
            return Response({'error': "logo_size_percentage must be between 5 and 30"}, status=400)
    except ValueError:
        return Response({'error': "logo_size_percentage must be an integer"}, status=400)
    
    # Find the image
    with open(json_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    item = None
    for entry in data_dict.values():
        if entry['title'].lower() == title.lower():
            item = entry
            break
    
    if not item:
        return Response({'error': "Image with the given title not found"}, status=404)
    
    # Get image dimensions
    filename = os.path.basename(item['filepath'])
    image_path = os.path.join(images_dir, filename)
    
    if not os.path.exists(image_path):
        return Response({'error': "Image file not found on server"}, status=404)
    
    try:
        with Image.open(image_path) as img:
            main_width, main_height = img.size
        
        # Calculate logo dimensions (assuming 1:1 aspect ratio for preview)
        new_logo_width = int(main_width * (logo_size_percentage / 100))
        new_logo_height = new_logo_width  # Assume square logo for preview
        
        # Ensure logo doesn't exceed bounds
        max_size = min(main_width - (2 * logo_padding), main_height - (2 * logo_padding))
        if new_logo_width > max_size:
            new_logo_width = new_logo_height = max_size
        
        return Response({
            'original_size': {
                'width': main_width,
                'height': main_height
            },
            'logo_size': {
                'width': new_logo_width,
                'height': new_logo_height,
                'percentage_of_width': round((new_logo_width / main_width) * 100, 2)
            },
            'logo_position': {
                'x': logo_padding,
                'y': logo_padding,
                'corner': 'top-left'
            },
            'filename': filename
        })
        
    except Exception as e:
        return Response({
            'error': f"Failed to read image: {str(e)}"
        }, status=500)


