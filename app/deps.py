from fastapi import Request


async def form_data(request: Request) -> dict:
    """Reads submitted form fields as a plain dict (used with Depends)."""
    return dict(await request.form())
