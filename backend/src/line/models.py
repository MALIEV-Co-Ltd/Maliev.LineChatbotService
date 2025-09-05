"""LINE webhook event models."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class LineUser(BaseModel):
    """LINE user information."""
    userId: str
    displayName: Optional[str] = None
    pictureUrl: Optional[str] = None
    statusMessage: Optional[str] = None


class LineSource(BaseModel):
    """LINE event source information."""
    type: str  # user, group, room
    userId: Optional[str] = None
    groupId: Optional[str] = None
    roomId: Optional[str] = None


class LineMessage(BaseModel):
    """LINE message information."""
    id: str
    type: str  # text, image, video, audio, file, location, sticker
    text: Optional[str] = None
    packageId: Optional[str] = None
    stickerId: Optional[str] = None


class LinePostback(BaseModel):
    """LINE postback information."""
    data: str
    params: Optional[Dict[str, Any]] = None


class LineEvent(BaseModel):
    """Base LINE webhook event."""
    type: str
    mode: str = "active"
    timestamp: int
    source: LineSource
    webhookEventId: str
    deliveryContext: Dict[str, Any] = Field(default_factory=dict)


class MessageEvent(LineEvent):
    """LINE message event."""
    type: str = "message"
    replyToken: str
    message: LineMessage


class FollowEvent(LineEvent):
    """LINE follow event."""
    type: str = "follow"
    replyToken: str


class UnfollowEvent(LineEvent):
    """LINE unfollow event."""
    type: str = "unfollow"


class PostbackEvent(LineEvent):
    """LINE postback event."""
    type: str = "postback"
    replyToken: str
    postback: LinePostback


class LineWebhookRequest(BaseModel):
    """LINE webhook request."""
    destination: str
    events: List[LineEvent]