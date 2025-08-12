from django.shortcuts import render
from django.core.paginator import Paginator
import os, json, time

def NewsDashboard_view(request):
    # ===== USER CONTEXT =====
    context = {}
    if request.user.is_authenticated:
        context.update({
            'user_id': request.user.id,
            'username': request.user.username,
        })

    # ===== PATHS / CONFIG =====
    BASE_EXTERNAL_PATH = '/home/anews/PS/gan'
    json_path = os.path.join(BASE_EXTERNAL_PATH, 'generated_history.json')
    crypto_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'crypto_news_images')
    custom_images_dir = os.path.join(BASE_EXTERNAL_PATH, 'custom_images')
    crypto_dir_name = 'crypto_news_images'
    custom_dir_name = 'custom_images'
    allowed_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

    # ===== LOAD JSON (if present) =====
    data = []
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
            # keep JSON order but latest first:
            data = list(data_dict.values())[::-1]
    except Exception:
        # missing/invalid JSON: keep going (we'll still scan directories)
        data = []

    # ===== NORMALIZE JSON ITEMS: set filepath & image_source & timestamp (epoch seconds) =====
    seen_filenames = set()
    for item in data:
        orig_fp = item.get('filepath', '') or ''
        filename = os.path.basename(orig_fp)
        if not filename:
            # skip items without a filename
            continue

        seen_filenames.add(filename)

        custom_fp = os.path.join(custom_images_dir, filename)
        crypto_fp = os.path.join(crypto_images_dir, filename)
        exists_custom = os.path.exists(custom_fp)
        exists_crypto = os.path.exists(crypto_fp)

        # prefer custom path when both exist, but mark 'both'
        if exists_custom and exists_crypto:
            item['filepath'] = f"/{custom_dir_name}/{filename}"
            item['image_source'] = 'both'
            item['timestamp'] = item.get('timestamp') or os.path.getmtime(custom_fp)
        elif exists_custom:
            item['filepath'] = f"/{custom_dir_name}/{filename}"
            item['image_source'] = 'custom'
            item['timestamp'] = item.get('timestamp') or os.path.getmtime(custom_fp)
        elif exists_crypto:
            item['filepath'] = f"/{crypto_dir_name}/{filename}"
            item['image_source'] = 'crypto'
            item['timestamp'] = item.get('timestamp') or os.path.getmtime(crypto_fp)
        else:
            # file missing locally: keep whatever filepath the JSON had and mark unknown
            item['image_source'] = item.get('image_source', 'unknown')
            # try to keep existing timestamp if present; otherwise leave None

    # ===== SCAN BOTH DIRECTORIES AND ADD FILES NOT MENTIONED IN JSON =====
    for dir_path, dir_name, source in (
        (custom_images_dir, custom_dir_name, 'custom'),
        (crypto_images_dir, crypto_dir_name, 'crypto'),
    ):
        try:
            for fname in os.listdir(dir_path):
                _, ext = os.path.splitext(fname)
                if ext.lower() not in allowed_exts:
                    continue

                # if we've already seen this filename in JSON, ensure image_source is set properly
                if fname in seen_filenames:
                    # mark existing item as 'both' if it exists in the other dir too
                    for it in data:
                        it_name = os.path.basename(it.get('filepath', ''))
                        if it_name == fname:
                            if it.get('image_source') and it['image_source'] != source and it['image_source'] != 'both':
                                it['image_source'] = 'both'
                    continue

                # otherwise create a minimal item for the file
                fullpath = os.path.join(dir_path, fname)
                try:
                    mtime = os.path.getmtime(fullpath)
                except OSError:
                    mtime = None

                new_item = {
                    'title': os.path.splitext(fname)[0],
                    'prompt': '',
                    'negative_prompt': '',
                    'filepath': f"/{dir_name}/{fname}",
                    'image_source': source,
                    'timestamp': mtime,
                }
                seen_filenames.add(fname)
                data.append(new_item)
        except FileNotFoundError:
            # directory missing: ignore
            continue

    # ===== SORT (most recent first) =====
    # Items without timestamp get pushed to the end
    data.sort(key=lambda it: it.get('timestamp') or 0, reverse=True)

    # ===== FILTERING =====
    filter_type = request.GET.get('filter', 'all').lower()
    if filter_type != 'all':
        filtered = []
        now = time.time()
        seven_days = 7 * 24 * 3600

        for item in data:
            title_lower = item.get('title', '').lower()
            prompt_lower = item.get('prompt', '').lower()
            src = item.get('image_source', '').lower()

            if filter_type == 'recent':
                ts = item.get('timestamp')
                if ts and ts >= (now - seven_days):
                    filtered.append(item)
            elif filter_type == 'bitcoin' and ('bitcoin' in title_lower or 'bitcoin' in prompt_lower or 'btc' in title_lower or 'btc' in prompt_lower):
                filtered.append(item)
            elif filter_type == 'ethereum' and ('ethereum' in title_lower or 'ethereum' in prompt_lower or 'eth' in title_lower or 'eth' in prompt_lower):
                filtered.append(item)
            elif filter_type == 'defi' and ('defi' in title_lower or 'defi' in prompt_lower or 'decentralized' in title_lower or 'decentralized' in prompt_lower):
                filtered.append(item)
            elif filter_type == 'crypto_images' and (src == 'crypto' or src == 'both'):
                filtered.append(item)
            elif filter_type == 'custom_images' and (src == 'custom' or src == 'both'):
                filtered.append(item)
            # else: not matched -> skip

        data = filtered

    # ===== PAGINATION =====
    paginator = Paginator(data, 6)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ===== CONTEXT & RENDER =====
    context['page_obj'] = page_obj
    context['current_filter'] = filter_type

    return render(request, 'NewsDashboard/NewsDashboard.html', context)
