"""FastAPI application for Lost & Found Service.

# TODO (Task 1 - HTTP API):
# Implement the 4 endpoints required by Section 5.1.2:
# 1. POST /items/lost
#    - Multipart upload: image (UploadFile), user_text (Form)
#    - Validates image format and size
#    - Saves blob and registers item with ItemStatus.LOST
#    - Returns ItemResponse
# 2. POST /items/found
#    - Same as /items/lost, but registers with ItemStatus.FOUND
# 3. GET /items/{id}/matches?k=N
#    - Calls item_service.find_matches(item_id, k=k)
#    - Returns MatchQueryResponse (top-k matches from opposite pool with similarity scores & reasons)
# 4. GET /items?status=lost|found
#    - Calls item_service.list_items(status=status)
#    - Returns list[ItemResponse]
"""

from fastapi import FastAPI

app = FastAPI(title="Smart Lost & Found API", version="1.0.0")


@app.get("/")
async def root():
    return {"message": "Smart Lost & Found API is running"}