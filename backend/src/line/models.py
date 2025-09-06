"""LINE webhook event models."""

from typing import Any

from pydantic import BaseModel, Field


class LineUser(BaseModel):
    """LINE user information."""
    userId: str
    displayName: str | None = None
    pictureUrl: str | None = None
    statusMessage: str | None = None


class LineSource(BaseModel):
    """LINE event source information."""
    type: str  # user, group, room
    userId: str | None = None
    groupId: str | None = None
    roomId: str | None = None


class LineMessage(BaseModel):
    """LINE message information."""
    id: str
    type: str  # text, image, video, audio, file, location, sticker
    text: str | None = None
    packageId: str | None = None
    stickerId: str | None = None


class LinePostback(BaseModel):
    """LINE postback information."""
    data: str
    params: dict[str, Any] | None = None


class LineEvent(BaseModel):
    """Base LINE webhook event."""
    type: str
    mode: str = "active"
    timestamp: int
    source: LineSource
    webhookEventId: str
    deliveryContext: dict[str, Any] = Field(default_factory=dict)


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
    events: list[LineEvent]
