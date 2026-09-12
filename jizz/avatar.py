"""Resize user avatars on upload so the header does not decode huge JPEGs."""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError

AVATAR_MAX_PX = 256


def resize_avatar_upload(uploaded):
    """Return a JPEG thumbnail of ``uploaded`` (max 256px on the long edge)."""
    try:
        image = Image.open(uploaded)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Invalid image.") from exc

    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    else:
        image = image.convert('RGB')

    image.thumbnail((AVATAR_MAX_PX, AVATAR_MAX_PX), Image.Resampling.LANCZOS)
    buf = BytesIO()
    image.save(buf, format='JPEG', quality=85, optimize=True)
    buf.seek(0)

    name = getattr(uploaded, 'name', None) or 'avatar.jpg'
    if '.' in name:
        name = name.rsplit('.', 1)[0] + '.jpg'
    else:
        name = f'{name}.jpg'

    return InMemoryUploadedFile(
        buf,
        'ImageField',
        name,
        'image/jpeg',
        buf.getbuffer().nbytes,
        None,
    )
