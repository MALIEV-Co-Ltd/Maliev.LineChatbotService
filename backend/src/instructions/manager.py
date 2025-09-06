"""Dynamic instruction system for context-aware AI responses."""

import re
from datetime import datetime
from typing import Any

import structlog

from ..customers.manager import customer_manager
from ..database.redis_client import redis_client

logger = structlog.get_logger("instructions")


class InstructionManager:
    """Manages dynamic system instructions based on conversation context."""

    def __init__(self):
        """Initialize instruction manager."""
        self._initialized = False

        # Domain detection patterns for 3D printing business
        self._domain_patterns = {
            "3d_printing": [
                r"(?:3d|สามมิติ|พิมพ์|print|printing|printer)",
                r"(?:filament|เส้น|วัสดุ|pla|abs|petg)",
                r"(?:โมเดล|model|แบบ|design|stl)",
                r"(?:layer|ชั้น|resolution|ความละเอียด)"
            ],
            "pricing": [
                r"(?:ราคา|price|cost|เท่าไหร่|กี่บาท)",
                r"(?:ค่าใช้จ่าย|ขาย|สั่ง|order)",
                r"(?:ประมาณ|estimate|quote|quotation)"
            ],
            "technical": [
                r"(?:ปัญหา|problem|issue|error|ผิดพลาด)",
                r"(?:setting|ตั้งค่า|config|configure)",
                r"(?:support|รองรับ|infill|เติม)",
                r"(?:temperature|อุณหภูมิ|speed|ความเร็ว)"
            ],
            "materials": [
                r"(?:วัสดุ|material|plastic|พลาสติก)",
                r"(?:pla|abs|petg|tpu|wood|metal)",
                r"(?:strength|แข็งแรง|flexible|ยืดหยุ่น)",
                r"(?:color|สี|transparent|ใส)"
            ],
            "service": [
                r"(?:บริการ|service|ช่วย|help)",
                r"(?:จัดส่ง|delivery|ship|ส่ง)",
                r"(?:รับ|accept|สามารถ|can)",
                r"(?:เวลา|time|duration|นาน)"
            ]
        }

        # Business context keywords
        self._business_keywords = {
            "urgent": ["ด่วน", "เร่งด่วน", "urgent", "asap", "รีบ"],
            "budget": ["งบ", "budget", "ถูก", "cheap", "expensive", "แพง"],
            "quality": ["คุณภาพ", "quality", "ดี", "good", "เยี่ยม", "excellent"],
            "beginner": ["มือใหม่", "beginner", "ไม่เคย", "never", "แรก", "first"],
            "professional": ["มืออาชีพ", "professional", "business", "commercial"]
        }

    async def initialize(self):
        """Initialize instruction system with default templates."""
        if self._initialized:
            return

        try:
            # Create default instruction templates
            await self._create_default_instructions()

            logger.info("Dynamic instruction system initialized")
            self._initialized = True

        except Exception as e:
            logger.error("Failed to initialize instruction system", error=str(e))
            raise

    async def generate_dynamic_instructions(
        self,
        user_id: str,
        user_message: str,
        conversation_history: list[str] = None
    ) -> str:
        """Generate dynamic system instructions based on context."""

        if not self._initialized:
            await self.initialize()

        try:
            # Analyze conversation context
            context = await self._analyze_context(user_id, user_message, conversation_history or [])

            # Select relevant instruction templates
            selected_instructions = await self._select_instructions(context)

            # Combine and personalize instructions
            combined_instructions = await self._combine_instructions(selected_instructions, context)

            logger.info("Dynamic instructions generated",
                       user_id=user_id,
                       domains=context.get("domains", []),
                       instruction_count=len(selected_instructions))

            return combined_instructions

        except Exception as e:
            logger.error("Failed to generate dynamic instructions", user_id=user_id, error=str(e))
            return await self._get_default_instruction()

    async def _analyze_context(
        self,
        user_id: str,
        user_message: str,
        conversation_history: list[str]
    ) -> dict[str, Any]:
        """Analyze conversation context for instruction selection."""

        try:
            # Get customer profile
            customer = await customer_manager.get_customer(user_id)

            # Detect domains in current message
            current_domains = self._detect_domains(user_message)

            # Detect domains in conversation history
            history_text = " ".join(conversation_history[-10:])  # Last 10 messages
            history_domains = self._detect_domains(history_text)

            # Combine domains with weights
            all_domains = {}
            for domain in current_domains:
                all_domains[domain] = all_domains.get(domain, 0) + 2  # Current message has more weight
            for domain in history_domains:
                all_domains[domain] = all_domains.get(domain, 0) + 1

            # Detect business context
            business_context = self._detect_business_context(user_message + " " + history_text)

            # Determine conversation stage
            conversation_stage = self._determine_conversation_stage(user_message, conversation_history)

            # Customer segment analysis
            customer_segment = await self._analyze_customer_segment(customer)

            context = {
                "user_id": user_id,
                "domains": list(all_domains.keys()),
                "domain_weights": all_domains,
                "business_context": business_context,
                "conversation_stage": conversation_stage,
                "customer_segment": customer_segment,
                "customer_profile": customer,
                "message_length": len(user_message),
                "is_question": "?" in user_message or any(word in user_message.lower() for word in ["ไง", "อะไร", "ยังไง", "เท่าไหร่"])
            }

            return context

        except Exception as e:
            logger.error("Failed to analyze context", user_id=user_id, error=str(e))
            return {"domains": [], "business_context": {}, "conversation_stage": "inquiry"}

    def _detect_domains(self, text: str) -> list[str]:
        """Detect business domains in text."""

        detected_domains = []
        text_lower = text.lower()

        for domain, patterns in self._domain_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    detected_domains.append(domain)
                    break  # Only add domain once

        return detected_domains

    def _detect_business_context(self, text: str) -> dict[str, bool]:
        """Detect business context keywords."""

        context = {}
        text_lower = text.lower()

        for context_type, keywords in self._business_keywords.items():
            context[context_type] = any(keyword in text_lower for keyword in keywords)

        return context

    def _determine_conversation_stage(self, current_message: str, history: list[str]) -> str:
        """Determine what stage of conversation this is."""

        if not history:
            return "initial"

        message_lower = current_message.lower()

        # Greeting patterns
        if any(word in message_lower for word in ["สวัสดี", "hello", "hi", "เฮ้ย"]):
            return "greeting"

        # Question/inquiry patterns
        if any(word in message_lower for word in ["ถาม", "สอบถาม", "อยาก", "ต้องการ"]):
            return "inquiry"

        # Problem/support patterns
        if any(word in message_lower for word in ["ปัญหา", "ช่วย", "ไม่ได้", "ผิดพลาด"]):
            return "support"

        # Order/purchase patterns
        if any(word in message_lower for word in ["สั่ง", "ซื้อ", "order", "จอง"]):
            return "order"

        # Follow-up patterns
        if any(word in message_lower for word in ["แล้ว", "ต่อ", "เพิ่ม", "อีก"]):
            return "followup"

        return "conversation"

    async def _analyze_customer_segment(self, customer: dict[str, Any] | None) -> str:
        """Analyze customer segment for personalization."""

        if not customer:
            return "new"

        message_count = customer.get("message_count", 0)
        created_at = customer.get("created_at", "")

        # Calculate days since creation
        try:
            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days_since_creation = (datetime.utcnow() - created_date.replace(tzinfo=None)).days
        except:
            days_since_creation = 0

        # Segment logic
        if days_since_creation <= 1:
            return "new"
        elif message_count >= 50:
            return "vip"
        elif message_count >= 10:
            return "regular"
        else:
            return "occasional"

    async def _select_instructions(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Select relevant instruction templates based on context."""

        try:
            # Get all instruction templates
            instruction_keys = await redis_client.keys("instruction:*")
            selected = []

            for key in instruction_keys:
                instruction_data = await redis_client.hgetall(key)
                if not instruction_data or instruction_data.get("enabled", "false") != "true":
                    continue

                instruction_name = key.split(":")[-1]

                # Check if instruction matches context
                if await self._matches_context(instruction_data, context):
                    priority = int(instruction_data.get("priority", 1))
                    selected.append({
                        "name": instruction_name,
                        "content": instruction_data.get("content", ""),
                        "category": instruction_data.get("category", "general"),
                        "priority": priority,
                        "triggers": instruction_data.get("triggers", "").split(",")
                    })

            # Sort by priority (descending)
            selected.sort(key=lambda x: x["priority"], reverse=True)

            # Limit to top 5 instructions to avoid overly long prompts
            return selected[:5]

        except Exception as e:
            logger.error("Failed to select instructions", error=str(e))
            return []

    async def _matches_context(self, instruction_data: dict[str, Any], context: dict[str, Any]) -> bool:
        """Check if instruction template matches current context."""

        try:
            category = instruction_data.get("category", "")
            triggers = instruction_data.get("triggers", "").split(",")

            # Check category match
            domains = context.get("domains", [])
            if category in domains:
                return True

            # Check trigger keywords
            user_message = context.get("current_message", "")
            conversation_stage = context.get("conversation_stage", "")
            customer_segment = context.get("customer_segment", "")

            for trigger in triggers:
                trigger = trigger.strip().lower()
                if not trigger:
                    continue

                # Check if trigger matches any context element
                if (trigger in user_message.lower() or
                    trigger == conversation_stage or
                    trigger == customer_segment or
                    trigger in domains):
                    return True

            return False

        except Exception as e:
            logger.warning("Failed to match context", error=str(e))
            return False

    async def _combine_instructions(
        self,
        selected_instructions: list[dict[str, Any]],
        context: dict[str, Any]
    ) -> str:
        """Combine selected instructions into cohesive system prompt."""

        if not selected_instructions:
            return await self._get_default_instruction()

        try:
            # Start with base instruction
            base_instruction = """คุณคือผู้ช่วย AI สำหรับธุรกิจ 3D Printing ในประเทศไทย"""

            # Add context-specific instructions
            domain_instructions = []
            for instruction in selected_instructions:
                content = instruction["content"]

                # Replace variables with context data
                content = self._replace_variables(content, context)

                domain_instructions.append(content)

            # Combine all instructions
            combined = base_instruction
            if domain_instructions:
                combined += "\n\n" + "\n\n".join(domain_instructions)

            # Add personalization based on customer segment
            personalization = self._get_personalization_suffix(context)
            if personalization:
                combined += "\n\n" + personalization

            return combined

        except Exception as e:
            logger.error("Failed to combine instructions", error=str(e))
            return await self._get_default_instruction()

    def _replace_variables(self, content: str, context: dict[str, Any]) -> str:
        """Replace variables in instruction content with context values."""

        replacements = {
            "{customer_name}": context.get("customer_profile", {}).get("name", "คุณลูกค้า"),
            "{customer_segment}": context.get("customer_segment", ""),
            "{conversation_stage}": context.get("conversation_stage", ""),
            "{business_context}": ", ".join([k for k, v in context.get("business_context", {}).items() if v])
        }

        result = content
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, str(value))

        return result

    def _get_personalization_suffix(self, context: dict[str, Any]) -> str:
        """Get personalization suffix based on customer segment."""

        segment = context.get("customer_segment", "")

        personalizations = {
            "new": "ลูกค้าใหม่ต้องการความช่วยเหลือเป็นพิเศษ อธิบายให้ละเอียดและใช้ภาษาที่เข้าใจง่าย",
            "vip": "ลูกค้า VIP ใส่ใจในรายละเอียดและคุณภาพ ให้คำแนะนำระดับผู้เชี่ยวชาญ",
            "regular": "ลูกค้าประจำที่คุ้นเคยกับบริการ ตอบสั้นกระชับและตรงประเด็น",
            "occasional": "ลูกค้าที่มาใช้บริการเป็นครั้งคราว อธิบายให้ชัดเจนแต่ไม่ซ้ำซาก"
        }

        return personalizations.get(segment, "")

    async def _get_default_instruction(self) -> str:
        """Get default system instruction."""

        return """คุณคือผู้ช่วย AI สำหรับธุรกิจ 3D Printing ในประเทศไทย

บทบาทของคุณ:
- ให้คำแนะนำเกี่ยวกับการพิมพ์ 3D, วัสดุ, และเทคนิค
- ตอบคำถามเกี่ยวกับราคาและบริการต่างๆ
- แก้ไขปัญหาทางเทคนิค
- ให้ข้อมูลเกี่ยวกับผลิตภัณฑ์และการใช้งาน

คำแนะนำการตอบ:
- ใช้ภาษาไทยที่เป็นมิตรและเข้าใจง่าย
- ให้ข้อมูลที่แม่นยำและเป็นประโยชน์
- หากไม่แน่ใจ ให้แนะนำให้ติดต่อทีมงานโดยตรง
- ใช้อีโมจิให้เหมาะสมเพื่อให้การสนทนาน่าสนใจ"""

    async def _create_default_instructions(self):
        """Create default instruction templates."""

        default_instructions = [
            {
                "name": "3d_printing_general",
                "category": "3d_printing",
                "content": """เฉพาะเรื่อง 3D Printing:
- อธิบายเทคนิค layer, infill, support ให้เข้าใจง่าย
- แนะนำการตั้งค่าที่เหมาะสมสำหรับงานพิมพ์แต่ละประเภท
- ให้คำแนะนำการแก้ไขปัญหาทั่วไป เช่น warping, stringing
- เสนอทางเลือกวัสดุที่เหมาะกับการใช้งาน""",
                "triggers": "3d,พิมพ์,printing,model,โมเดล",
                "priority": 5
            },
            {
                "name": "pricing_service",
                "category": "pricing",
                "content": """เรื่องราคาและบริการ:
- ให้ราคาประมาณการที่ชัดเจน โดยระบุปัจจัยที่ส่งผลต่อราคา
- อธิบายค่าใช้จ่ายต่างๆ เช่น วัสดุ, เวลาพิมพ์, post-processing
- เสนอทางเลือกที่ประหยัดหากลูกค้าต้องการ
- แจ้งเวลาดำเนินการและข้อกำหนดการจัดส่ง""",
                "triggers": "ราคา,price,cost,เท่าไหร่,บาท",
                "priority": 4
            },
            {
                "name": "technical_support",
                "category": "technical",
                "content": """การแก้ไขปัญหาทางเทคนิค:
- วินิจฉัยปัญหาจากอาการที่ลูกค้าบอก
- ให้ขั้นตอนการแก้ไขที่ชัดเจน เรียงลำดับจากง่ายไปยาก
- อธิบายสาเหตุของปัญหาเพื่อป้องกันไม่ให้เกิดขึ้นอีก
- หากปัญหาซับซ้อน ให้แนะนำให้ส่งงานมาตรวจสอบ""",
                "triggers": "ปัญหา,problem,ผิดพลาด,error,ช่วย",
                "priority": 5
            },
            {
                "name": "materials_guide",
                "category": "materials",
                "content": """เรื่องวัสดุพิมพ์ 3D:
- แนะนำวัสดุที่เหมาะกับการใช้งานแต่ละประเภท
- อธิบายข้อดี-ข้อเสียของวัสดุแต่ละชนิด
- แนะนำการเก็บรักษาและการตั้งค่าเครื่องสำหรับวัสดุต่างๆ
- เปรียบเทียบราคาและคุณภาพของวัสดุ""",
                "triggers": "วัสดุ,material,pla,abs,petg,filament",
                "priority": 4
            },
            {
                "name": "new_customer_welcome",
                "category": "service",
                "content": """สำหรับลูกค้าใหม่:
- ทักทายอย่างอบอุ่นและแนะนำบริการโดยย่อ
- อธิบายขั้นตอนการทำงานและสิ่งที่ต้องเตรียม
- แนะนำตัวอย่างงานและราคาเบื้องต้น
- เสนอให้ปรึกษาฟรีสำหรับโปรเจคแรก""",
                "triggers": "new,ใหม่,แรก,first,ไม่เคย",
                "priority": 3
            }
        ]

        for instruction in default_instructions:
            instruction_key = f"instruction:{instruction['name']}"

            # Check if already exists
            exists = await redis_client.exists(instruction_key)
            if exists:
                continue

            # Create instruction data
            now = datetime.utcnow().isoformat()
            instruction_data = {
                "content": instruction["content"],
                "category": instruction["category"],
                "triggers": instruction["triggers"],
                "priority": str(instruction["priority"]),
                "enabled": "true",
                "created_at": now,
                "updated_at": now
            }

            # Store instruction
            for field, value in instruction_data.items():
                await redis_client.hset(instruction_key, field, value)

        logger.info("Default instruction templates created")


# Global instruction manager instance
instruction_manager = InstructionManager()
