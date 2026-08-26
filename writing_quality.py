"""
Writing Quality Enhancements for BookGPT.

This module implements four major quality improvements:
1. Multi-Draft Writing Process - Multiple passes (rough, structural, line edit, proofread)
2. Self-Critique Loop - Agent reads its own work, critiques, and rewrites weak sections
3. Style Transfer & Author Mimicry - Emulate specific author voices with few-shot examples
4. Structural Templates - Save the Cat and Hero's Journey beat sheets for chapter structure
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 1. MULTI-DRAFT WRITING PROCESS
# =============================================================================

DRAFT_PASSES = {
    'rough': {
        'name': 'Rough Draft',
        'system_prompt_addition': """This is a ROUGH DRAFT. Focus on:
- Getting the story down quickly
- Plot momentum and forward motion
- Scene structure and beats
- Character actions and dialogue
Do NOT worry about perfect prose, word choice, or polish. Get the bones right.
The goal is a complete, structurally sound draft with good pacing.""",
        'max_tokens': 8000,
        'temperature': 0.8
    },
    'structural': {
        'name': 'Structural Edit',
        'system_prompt_addition': """This is a STRUCTURAL EDIT pass. Focus on:
- Pacing: cut slow sections, expand rushed ones
- Scene order: ensure logical flow
- Arc strengthening: deepen character development
- Adding missing scenes (transitions, emotional beats)
- Cutting filler and redundant scenes
- Ensuring each scene has a clear purpose
Rewrite with improved structure while keeping the core story intact.""",
        'max_tokens': 8000,
        'temperature': 0.7
    },
    'line_edit': {
        'name': 'Line Edit',
        'system_prompt_addition': """This is a LINE EDIT pass. Focus on prose-level polish:
- Word choice: stronger verbs, precise nouns
- Sentence rhythm and variation
- Sensory details and imagery
- Show don't tell (replace "She was sad" with showing)
- Dialogue tightening
- Cutting adverbs and weak modifiers
- Voice and tone consistency
Polish every sentence. This is where the prose comes alive.""",
        'max_tokens': 8000,
        'temperature': 0.65
    },
    'proofread': {
        'name': 'Proofread',
        'system_prompt_addition': """This is a PROOFREADING pass. Focus on:
- Grammar and punctuation errors
- Spelling and typos
- Consistency (names, dates, facts)
- Formatting consistency
Do NOT make stylistic changes. Only fix errors.""",
        'max_tokens': 8000,
        'temperature': 0.3
    }
}

DEFAULT_DRAFT_SEQUENCE = ['rough', 'structural', 'line_edit', 'proofread']


def get_draft_pass_config(pass_name: str) -> Dict[str, Any]:
    """Get configuration for a specific draft pass."""
    return DRAFT_PASSES.get(pass_name, DRAFT_PASSES['rough'])


def build_draft_prompt(pass_name: str, base_content: str, chapter_info: Dict[str, Any]) -> str:
    """Build a prompt for a specific draft pass."""
    config = get_draft_pass_config(pass_name)
    
    if pass_name == 'rough':
        return None  # Rough draft uses the standard writing prompt
    
    # For subsequent passes, we revise the existing content
    return f"""Revise this chapter draft with a {config['name']} pass.

Chapter {chapter_info.get('chapter_number', '?')}: {chapter_info.get('title', '')}
Genre: {chapter_info.get('genre', '')}

Current draft:
---
{base_content}
---

{config['system_prompt_addition']}

Return the COMPLETE revised chapter. Do not summarize or truncate."""


# =============================================================================
# 2. SELF-CRITIQUE LOOP
# =============================================================================

CRITIQUE_RUBRIC = {
    'pacing': {
        'description': 'Does the chapter move at the right speed? Are there slow spots or rushed sections?',
        'weight': 1
    },
    'dialogue': {
        'description': 'Is dialogue natural and character-revealing? Does it advance plot or develop character?',
        'weight': 1
    },
    'sensory_detail': {
        'description': 'Are there vivid sensory details? Does the reader see, hear, smell, feel the scene?',
        'weight': 1
    },
    'conflict': {
        'description': 'Is there clear conflict or tension? Does something matter to the protagonist?',
        'weight': 1
    },
    'character_voice': {
        'description': 'Do characters sound distinct? Is the POV character\'s voice consistent?',
        'weight': 1
    },
    'show_dont_tell': {
        'description': 'Does the writing show rather than tell? Are emotions conveyed through action?',
        'weight': 1
    },
    'scene_structure': {
        'description': 'Does each scene have a goal, conflict, and outcome? Are transitions smooth?',
        'weight': 1
    }
}


def build_critique_prompt(chapter_content: str, chapter_info: Dict[str, Any]) -> str:
    """Build a prompt for the self-critique pass."""
    rubric_text = "\n".join([
        f"- {key}: {item['description']}"
        for key, item in CRITIQUE_RUBRIC.items()
    ])
    
    return f"""You are a master editor critiquing this chapter. Score each criterion 1-10 and provide specific, actionable feedback.

Chapter {chapter_info.get('chapter_number', '?')}: {chapter_info.get('title', '')}
Genre: {chapter_info.get('genre', '')}

Chapter content:
---
{chapter_content[:4000]}
---

Score each criterion (1-10) and give specific suggestions:

{rubric_text}

Also identify:
1. The 3 WEAKEST sections (quote the exact text)
2. Specific rewrite suggestions for each weak section

Format your response as:
SCORES:
- pacing: [1-10]
- dialogue: [1-10]
- sensory_detail: [1-10]
- conflict: [1-10]
- character_voice: [1-10]
- show_dont_tell: [1-10]
- scene_structure: [1-10]
OVERALL: [average]

WEAK SECTIONS:
1. "[quote]" → [suggestion]
2. "[quote]" → [suggestion]
3. "[quote]" → [suggestion]"""


def build_rewrite_prompt(chapter_content: str, critique: str, chapter_info: Dict[str, Any]) -> str:
    """Build a prompt to rewrite weak sections based on critique."""
    return f"""Rewrite this chapter addressing the critique below. Apply the specific suggestions to improve the weak sections.

Chapter {chapter_info.get('chapter_number', '?')}: {chapter_info.get('title', '')}

Original chapter:
---
{chapter_content}
---

Critique and suggestions:
---
{critique}
---

Rewrite the COMPLETE chapter with the improvements applied. Maintain the story and character arcs while elevating the prose quality."""


# =============================================================================
# 3. STYLE TRANSFER & AUTHOR MIMICRY
# =============================================================================

# Reuse DEFAULT_WRITING_STYLES from version_model but add few-shot examples
STYLE_EXAMPLES = {
    'hemingway': {
        'name': 'Hemingway / Minimalist',
        'description': 'Sparse, direct prose with short sentences. Focus on action and dialogue over description.',
        'system_prompt': 'Write in a minimalist style with short, declarative sentences. Avoid adverbs and excessive description. Focus on action and dialogue. Let subtext carry emotional weight.',
        'example': """The old man sat in the chair. He looked at the wall. The wall was white and had been white for a long time. He did not move. Outside, the rain fell on the street. It had been raining for three days. He did not mind the rain. He minded the quiet.""",
        'traits': ['concise', 'direct', 'action-focused']
    },
    'literary': {
        'name': 'Literary Fiction',
        'description': 'Lyrical, introspective prose with focus on character development and thematic depth.',
        'system_prompt': 'Write with literary precision. Use evocative language, complex sentences, and rich imagery. Focus on character interiority and thematic resonance.',
        'example': """The light fell through the window in long, amber slants, catching the dust that drifted like memory through the room. She had sat in this chair a thousand times, yet today the familiar felt foreign, as though the house itself had shifted on its foundation overnight, realigning itself to some new truth she could not yet name.""",
        'traits': ['lyrical', 'introspective', 'thematic']
    },
    'thriller': {
        'name': 'Thriller / Page-Turner',
        'description': 'Fast-paced, tension-filled prose with short chapters and cliffhangers.',
        'system_prompt': 'Write fast-paced, tension-filled prose. Use short paragraphs and chapter cliffhangers. Focus on pacing and suspense. Every scene should advance the plot.',
        'example': """The door handle turned. Slowly. She held her breath. The hinges didn't creak—they never did—but she heard footsteps. Two sets. She counted the floorboards under the bed. Fourteen to the window. Seven to the closet. The footsteps stopped outside the bedroom door. The knob turned again. She had seven seconds to decide.""",
        'traits': ['fast-paced', 'tension', 'suspenseful']
    },
    'romance': {
        'name': 'Romance',
        'description': 'Emotional, character-driven prose with focus on relationships and dialogue.',
        'system_prompt': 'Write emotionally engaging romance. Focus on character chemistry and relationship development. Use witty dialogue and emotional introspection. Build tension and satisfying resolution.',
        'example': """He was looking at her the way he used to, before everything fell apart. The way that made her forget why she'd ever thought leaving was the answer. "You came," he said, and the two words carried three years of silence, of almost-calls, of nights spent staring at the phone. She hadn't meant to come. That was the problem with love—it didn't ask permission.""",
        'traits': ['emotional', 'character-driven', 'dialogue-rich']
    },
    'scifi': {
        'name': 'Science Fiction',
        'description': 'Technical, world-building prose with concepts and ideas at the forefront.',
        'system_prompt': 'Write science fiction with focus on world-building and concepts. Balance technical exposition with character moments. Use clear, precise language for scientific concepts.',
        'example': """The ansible had been silent for fourteen years. Now it sang—a low harmonic that vibrated through the ship's hull like a heartbeat returning to a frozen chest. Mira pressed her palm to the bulkhead and felt it: data, streaming in from a colony that had died in her grandmother's lifetime. Someone, or something, was calling home.""",
        'traits': ['technical', 'world-building', 'conceptual']
    },
    'fantasy': {
        'name': 'Fantasy Epic',
        'description': 'Rich, immersive prose with detailed world-building and epic scope.',
        'system_prompt': 'Write epic fantasy with rich world-building. Use sensory detail to bring settings to life. Balance action with lore. Create memorable characters with clear motivations.',
        'example': """The tower rose from the mountain like a spine of bone, white against the grey sky, older than the kingdom that sprawled at its feet. Dragons had carved it from the living rock in the age before ages, when the world was young and the gods still walked the valleys. Now only the wind climbed its stairs, and the echo of forgotten names.""",
        'traits': ['immersive', 'world-building', 'epic']
    },
    'technical': {
        'name': 'Technical / Educational',
        'description': 'Clear, structured prose for educational or technical content.',
        'system_prompt': 'Write clear, structured technical content. Use examples and explanations. Organize information logically. Define technical terms when first introduced.',
        'example': """Functions are the building blocks of any program. Think of a function as a recipe: it takes ingredients (inputs), performs steps (instructions), and produces a result (output). This separation of concerns—input, process, output—is what makes functions reusable and your code maintainable.""",
        'traits': ['clear', 'structured', 'educational']
    },
    'poetic': {
        'name': 'Poetic / Lyrical',
        'description': 'Beautiful, rhythmic prose with focus on imagery and sound.',
        'system_prompt': 'Write with poetic beauty. Use rhythm, alliteration, and vivid imagery. Let the sound of words enhance meaning. Create passages that reward re-reading.',
        'example': """The river remembered. It carried in its current the silt of mountains ground to powder, the bones of forests drowned in spring floods, the silver scales of fish that had lived and died in its depths without witness. It remembered the bridge that had crossed it, the lovers who had stood upon it, the wars that had stained its banks red beneath a moon that did not care.""",
        'traits': ['rhythmic', 'imagery-rich', 'beautiful']
    }
}


def get_style_config(style_key: str) -> Dict[str, Any]:
    """Get style configuration including few-shot example."""
    return STYLE_EXAMPLES.get(style_key, STYLE_EXAMPLES['literary'])


def build_style_prompt_addition(style_key: str) -> str:
    """Build a style-specific prompt addition with few-shot example."""
    style = get_style_config(style_key)
    return f"""

WRITING STYLE: {style['name']}
{style['system_prompt']}

Example of this style:
{style['example']}

Emulate this voice and style in your writing."""


# =============================================================================
# 4. STRUCTURAL TEMPLATES (Beat Sheets)
# =============================================================================

STRUCTURAL_TEMPLATES = {
    'save_the_cat': {
        'name': 'Save the Cat (Blake Snyder)',
        'description': '15-beat structure for commercial fiction and screenplays',
        'beats': [
            {'name': 'Opening Image', 'position': 0.0, 'description': 'Set the tone, introduce the protagonist in their normal world'},
            {'name': 'Theme Stated', 'position': 0.05, 'description': 'Someone states the theme or central question (often unknowingly)'},
            {'name': 'Setup', 'position': 0.10, 'description': 'Introduce the protagonist, their flaws, and their world'},
            {'name': 'Catalyst', 'position': 0.12, 'description': 'The inciting incident that disrupts the status quo'},
            {'name': 'Debate', 'position': 0.20, 'description': 'The protagonist hesitates, resists the call to adventure'},
            {'name': 'Break into Two', 'position': 0.25, 'description': 'The protagonist makes a choice and crosses into the new world'},
            {'name': 'B Story', 'position': 0.30, 'description': 'A subplot (often romance) begins, reflecting the theme'},
            {'name': 'Fun and Games', 'position': 0.40, 'description': 'The "promise of the premise" — exploration of the new world'},
            {'name': 'Midpoint', 'position': 0.50, 'description': 'False victory or false defeat, stakes raised'},
            {'name': 'Bad Guys Close In', 'position': 0.60, 'description': 'External and internal pressures mount, team fractures'},
            {'name': 'All Is Lost', 'position': 0.75, 'description': 'The lowest point, a major loss, the "whiff of death"'},
            {'name': 'Dark Night of the Soul', 'position': 0.80, 'description': 'The protagonist grapples with defeat before finding a way forward'},
            {'name': 'Break into Three', 'position': 0.85, 'description': 'The "Aha!" moment, synthesis of what was learned'},
            {'name': 'Finale', 'position': 0.95, 'description': 'The protagonist applies what they learned, final confrontation'},
            {'name': 'Final Image', 'position': 1.0, 'description': 'Contrast with the opening image, showing transformation'}
        ]
    },
    'heros_journey': {
        'name': 'The Hero\'s Journey (Joseph Campbell)',
        'description': '12-stage mythic structure for epic and fantasy narratives',
        'beats': [
            {'name': 'Ordinary World', 'position': 0.0, 'description': 'The hero\'s normal life before the story begins'},
            {'name': 'Call to Adventure', 'position': 0.10, 'description': 'The hero is presented with a challenge or quest'},
            {'name': 'Refusal of the Call', 'position': 0.15, 'description': 'The hero hesitates or refuses out of fear'},
            {'name': 'Meeting the Mentor', 'position': 0.20, 'description': 'A mentor appears to give guidance or tools'},
            {'name': 'Crossing the Threshold', 'position': 0.25, 'description': 'The hero commits to the journey, leaving the known world'},
            {'name': 'Tests, Allies, Enemies', 'position': 0.35, 'description': 'The hero learns the rules of the new world'},
            {'name': 'Approach to the Inmost Cave', 'position': 0.45, 'description': 'Preparation for the major challenge'},
            {'name': 'The Ordeal', 'position': 0.50, 'description': 'The hero confronts their greatest fear, death and rebirth'},
            {'name': 'Reward (Seizing the Sword)', 'position': 0.60, 'description': 'The hero claims a treasure after surviving the ordeal'},
            {'name': 'The Road Back', 'position': 0.70, 'description': 'The hero begins the return, but faces consequences'},
            {'name': 'Resurrection', 'position': 0.85, 'description': 'A final test of transformation, the climax'},
            {'name': 'Return with the Elixir', 'position': 1.0, 'description': 'The hero returns home transformed, with a gift for the world'}
        ]
    },
    'three_act': {
        'name': 'Three-Act Structure',
        'description': 'Classic beginning-middle-end structure',
        'beats': [
            {'name': 'Act I: Setup', 'position': 0.0, 'description': 'Establish world, characters, and the status quo'},
            {'name': 'Inciting Incident', 'position': 0.10, 'description': 'The event that sets the story in motion'},
            {'name': 'Plot Point 1', 'position': 0.25, 'description': 'The protagonist commits to the story, Act I ends'},
            {'name': 'Act II: Confrontation', 'position': 0.30, 'description': 'Rising action, obstacles, complications'},
            {'name': 'Midpoint', 'position': 0.50, 'description': 'A reversal or revelation raises the stakes'},
            {'name': 'Plot Point 2', 'position': 0.75, 'description': 'A crisis that propels into Act III'},
            {'name': 'Act III: Resolution', 'position': 0.80, 'description': 'The climax and falling action'},
            {'name': 'Climax', 'position': 0.90, 'description': 'The final confrontation, highest tension'},
            {'name': 'Resolution', 'position': 1.0, 'description': 'Loose ends tied, new status quo established'}
        ]
    },
    'seven_point': {
        'name': 'Seven-Point Story Structure (Dan Wells)',
        'description': 'A compact structure for tight plotting',
        'beats': [
            {'name': 'Hook', 'position': 0.0, 'description': 'The opposite of the resolution — show who the character is before'},
            {'name': 'Plot Turn 1', 'position': 0.15, 'description': 'The world shifts, the story begins'},
            {'name': 'Pinch Point 1', 'position': 0.30, 'description': 'Pressure applied, the antagonist revealed'},
            {'name': 'Midpoint', 'position': 0.50, 'description': 'The character moves from reaction to action'},
            {'name': 'Pinch Point 2', 'position': 0.70, 'description': 'More pressure, things look dire'},
            {'name': 'Plot Turn 2', 'position': 0.85, 'description': 'The final piece needed for the resolution'},
            {'name': 'Resolution', 'position': 1.0, 'description': 'The opposite of the hook — the character is transformed'}
        ]
    },
    'freytag': {
        'name': 'Freytag\'s Pyramid',
        'description': 'Classic dramatic structure with five parts',
        'beats': [
            {'name': 'Exposition', 'position': 0.0, 'description': 'Background, setting, characters introduced'},
            {'name': 'Rising Action', 'position': 0.20, 'description': 'A series of events building to the climax'},
            {'name': 'Climax', 'position': 0.50, 'description': 'The turning point, highest tension'},
            {'name': 'Falling Action', 'position': 0.70, 'description': 'The conflict begins to resolve'},
            {'name': 'Denouement', 'position': 1.0, 'description': 'Final resolution, all conflicts resolved'}
        ]
    },
    'none': {
        'name': 'No Structure Template',
        'description': 'Let the agent determine the structure freely',
        'beats': []
    }
}


def get_structure_template(template_key: str) -> Dict[str, Any]:
    """Get a structural template by key."""
    return STRUCTURAL_TEMPLATES.get(template_key, STRUCTURAL_TEMPLATES['three_act'])


def build_structure_prompt_addition(template_key: str, total_chapters: int) -> str:
    """Build a prompt addition that maps beats to chapter positions."""
    template = get_structure_template(template_key)
    if not template['beats']:
        return ""
    
    beat_mapping = []
    for beat in template['beats']:
        chapter = max(1, round(beat['position'] * total_chapters))
        beat_mapping.append(f"  - Chapter {chapter} ({int(beat['position']*100)}%): {beat['name']} — {beat['description']}")
    
    return f"""

STRUCTURAL TEMPLATE: {template['name']}
{template['description']}

Map your chapters to these story beats:
{chr(10).join(beat_mapping)}

Ensure each chapter serves its assigned beat and advances the overall structure."""


def get_beat_for_chapter(template_key: str, chapter_number: int, total_chapters: int) -> Optional[Dict[str, Any]]:
    """Get the beat that corresponds to a specific chapter."""
    template = get_structure_template(template_key)
    if not template['beats']:
        return None
    
    chapter_position = chapter_number / max(total_chapters, 1)
    
    # Find the closest beat
    closest_beat = None
    closest_diff = float('inf')
    for beat in template['beats']:
        diff = abs(beat['position'] - chapter_position)
        if diff < closest_diff:
            closest_diff = diff
            closest_beat = beat
    
    return closest_beat