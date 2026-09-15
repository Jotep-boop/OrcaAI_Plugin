# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.orcaslicer.plugin]
# name = "Orca AI"
# description = "Context-aware OrcaSlicer help through the OpenAI Responses API."
# author = "Jeppe"
# version = "0.7.0-beta.1"
# ///

"""Orca AI 0.7.0-beta.1 for OrcaSlicer 2.5.0-dev build ac3997c0."""

import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import orca


OPENAI_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6-terra"
SYSTEM_PROMPT = """Du är Orca AI, en expert på FFF/FDM och OrcaSlicer.
Svara på svenska, konkret och lättläst. Utgå från projektkontexten. Låtsas
aldrig att du har
ändrat något: du är rådgivande och kan ännu inte skriva till OrcaSlicer.

VIKTIGT OM BYGGPLATTOR:
- model.project_extent_mm omfattar hela projektet och kan sträcka sig över flera
  byggplattor. Jämför ALDRIG detta mått med storleken på en enda byggplatta.
- Orcas plugin-API i denna version anger inte vilken platta varje objekt tillhör.
- Om plates.reported_count är större än antalet fångade plattor saknas underlag
  för minst en platta. Nämn detta endast när det påverkar den efterfrågade
  bedömningen. Gissa inte plattillhörighet från XY-läge.
- Använd endast settings.build_volume för bäddens verkliga mått. Gissa aldrig
  byggytan från skrivarens namn.
- Skilj på model.object_count och model.instance_count. Filnamn som innehåller
  x2/x4 är bara en möjlig ledtråd, aldrig bevis på önskat antal.
- object_count, instance_count och instance_count_in_slice_snapshot räknar
  Orca-objekt/instanser, INTE säkert fysiska lösa delar. En enda STL och en enda
  Orca-instans kan innehålla flera frånkopplade meshkroppar, till exempel fyra
  clamps i en fil med suffixet _x4. Skriv därför "ett skivat Orca-objekt från
  Belt_Clamp_x4.stl", aldrig "en Belt Clamp", om antal meshkomponenter saknas.
  Om användaren frågar om antal ska physical_part_count anges som okänt och
  preview/BOM föreslås som kontrollkälla.

FORMAT:
- Börja en projekt- eller utskriftskontroll med exakt en status: REDO,
  KONTROLLERA eller STOPP. Använd inte statusetiketten för vanliga sakfrågor.
- Prioritera verifierade avvikelser och konkreta råd. Upprepa inte samma
  reservation i flera avsnitt.
- Använd Markdown-rubriker, korta stycken och punktlistor. Använd ALDRIG
  Markdown-tabeller eller HTML; chattytan är för smal för tabeller.
- Lista inte varje inställning som redan är bra. Samla godkända kontroller kort.
- Nämn inte rutinmässiga kontroller av support, brim, orientering, bäddmarginal
  eller preview om projektdata inte visar ett konkret problem eller användaren
  frågar specifikt om dem. Att en funktion är avstängd är inte i sig ett fel.
- Resonera inte om antal utifrån suffix som x2/x4 om användaren inte uttryckligen
  frågar om antal, BOM eller saknade delar.
- Ta bara upp saknad information när den hindrar svaret eller kan ändra beslutet.
- Vid inställningsförslag: ange Orca-nyckel, nuvarande värde, förslag, orsak och
  viktig kompromiss i ett kort punktblock per inställning.
- Kalla inte en hastighet aggressiv enbart utifrån mm/s. Bedöm först lagerhöjd,
  linjebredd, filament_max_volumetric_speed och relevanta accelerationer. Om
  underlaget inte räcker ska du säga att hastigheten inte kan bedömas säkert;
  ge inte generella fasta hastighetsintervall som om de vore maskinens gräns.
- settings.derived_flow är en grov nominell beräkning, inte uppmätt flöde. Jämför
  den med filamentgränsen men beakta att acceleration, korta banor och slicerns
  dynamiska flödesbegränsning kan göra verklig hastighet lägre.
- fan_max_speed är ett tillåtet maxvärde, inte bevis för att fläkten alltid körs
  på den nivån. Bedöm kylning tillsammans med minfläkt, lagertid, första lager,
  överhängsfläkt och materialprofil. Föreslå inte en generell ABS-fläktprocent
  utan tydlig grund i profildata eller användarens utskriftsproblem.
- En sparad användarprofil kan vara kalibrerad. Rekommendera inte ändringar bara
  för att ett värde avviker från en allmän tumregel.
  Överskrid inte tillverkarens gränser utan tydlig varning.
- slicing.last_snapshot och slicing.plate_snapshots, om de finns, fångades under
  genomförd slicing. De är bättre grund för lager- och supportbedömning än
  oskivad modelldata, men kan vara gamla om projektet har ändrats efteråt.
- slicing.plate_snapshots innehåller ett snapshot per observerad platta. När två
  plattor finns och två snapshots har fångats ska du använda båda och inte säga
  att plattfördelningen saknas. Det generella model.objects saknar fortfarande
  plattillhörighet, men objekten i varje snapshot hör till just den plattan.
- slicing.analysis_scope är bindande. Om complete_for_reported_project är true
  och användarens fråga gäller projektet, utskriftskontroll, support eller
  orientering ska svaret behandla ALLA nummer i captured_plate_numbers. Skriv en
  kort rubrik per platta och därefter en gemensam slutsats. Begränsa aldrig
  analysen till den senast skivade plattan i detta läge.
- I AI-underlaget är analysis_contract och sliced_plates de auktoritativa
  källorna för skivade plattor. Varje post i sliced_plates bevisar att objekten
  ingick i just den slicingen. En printable-flagga från den aktiva GUI-plattans
  globala modelldata får ALDRIG användas för att kalla objekt på en annan fångad
  platta avstängda, exkluderade eller ej utskrivbara.
- Läs alltid slicing.observer_status innan du kommenterar saknad snapshot.
  Om status är not_selected ska du säga att observatören inte är vald i den
  aktiva processprofilen. Om status är selected_waiting ska du säga att den är
  vald men ännu inte har körts sedan pluginen laddades. Påstå inte att en platta
  är oskivad bara för att pluginen saknar ett snapshot.
- Ett slicing-snapshot gäller endast den platta som skivades. Blanda inte ihop
  dess objekt eller XY-utbredning med hela projektets model.project_extent_mm.
- sliced_xy_bbox_mm är objektlokal slicinggeometri kring objektets arbetsorigo.
  Två identiska objekt får därför ofta exakt samma min/max trots att de ligger
  långt ifrån varandra. Använd ALDRIG dessa boxar för att påstå överlapp,
  absolut bäddposition eller marginal mot bäddkanten.
- objects[].instances_in_slice_snapshot innehåller modellinstansernas placering
  och world_bbox i ett gemensamt projektkoordinatsystem. I samma snapshot kan
  separata world_bboxar bevisa att bounding-boxarna inte överlappar. Överlappande
  world_bboxar visar däremot bara möjlig kollision, inte faktisk meshkollision.
  Jämför dem inte med bäddens 0–bredd/0–djup eftersom aktuell plattas globala
  origo/offset inte exponeras. Auto-brimens slutliga kontur exponeras inte heller.
  Nämn inte dessa API-begränsningar om de saknar betydelse för frågan.
- Ställ en kort följdfråga endast när svaret faktiskt kräver den."""

EXPERIENCE_INSTRUCTIONS = {
    "beginner": """ERFARENHETSNIVÅ: NYBÖRJARE
- Förklara kort varför en avvikelse spelar roll och var den kontrolleras i Orca.
- Ta med högst tre relevanta förebyggande kontroller när de hjälper användaren.
- Undvik jargong eller förklara den med en kort mening.""",
    "experienced": """ERFARENHETSNIVÅ: ERFAREN
- Förutsätt att användaren kan OrcaSlicer och förstår support, brim och preview.
- Ta endast upp mätbara avvikelser, tydliga risker eller sådant användaren frågar om.
- Ge inte allmänna påminnelser om visuella kontroller eller etablerad grundpraxis.""",
    "expert": """ERFARENHETSNIVÅ: EXPERT
- Rapportera endast blockerande fel, mätbara gränsöverskridanden och direkt svar
  på frågan. Utelämna introduktioner, grundförklaringar och rutinråd.
- Var tekniskt precis och ange relevanta Orca-nycklar och värden.""",
}

RESPONSE_MODE_INSTRUCTIONS = {
    "quick": """SVARSLÄGE: SNABBKONTROLL
- Håll svaret till cirka 120 ord, om inte användaren uttryckligen ber om mer.
- Vid projektkontroll: en statusrad, en kompakt rad per fångad platta och högst
  tre åtgärder totalt. Om inget behöver göras, skriv ingen åtgärdslista.
- Sammanfatta godkända kontroller på högst en rad.""",
    "deep": """SVARSLÄGE: DJUP ANALYS
- Ge nödvändiga beräkningar och resonemang, men håll svaret under cirka 700 ord.
- Strukturera efter relevanta avvikelser; skapa inte avsnitt för sådant som saknar
  betydelse för frågan.""",
}


def _finite_number(name, value, *, positive=False, minimum=None, maximum=None):
    """Normalize a tuning input and reject values that would hide bad results."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} måste vara ett tal.") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} måste vara ett ändligt tal.")
    if positive and number <= 0:
        raise ValueError(f"{name} måste vara större än noll.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} måste vara minst {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} får högst vara {maximum}.")
    return number


def calculate_rotation_distance(current, requested, actual):
    """Klipper rotation_distance after a measured extruder movement."""
    current = _finite_number("Nuvarande rotation_distance", current, positive=True)
    requested = _finite_number("Begärd extrudering", requested, positive=True)
    actual = _finite_number("Uppmätt extrudering", actual, positive=True)
    return current * actual / requested


def calculate_e_steps(current, requested, actual):
    """Marlin/RepRapFirmware E-steps after a measured extruder movement."""
    current = _finite_number("Nuvarande E-steps", current, positive=True)
    requested = _finite_number("Begärd extrudering", requested, positive=True)
    actual = _finite_number("Uppmätt extrudering", actual, positive=True)
    return current * requested / actual


def calculate_flow_ratio(current, modifier, method="yolo"):
    """Apply Orca's YOLO or legacy two-pass flow-ratio modifier."""
    current = _finite_number("Nuvarande flow ratio", current, positive=True)
    modifier = _finite_number("Modifierare", modifier)
    if method == "yolo":
        result = current + modifier
    elif method == "two_pass":
        result = current * (100 + modifier) / 100
    else:
        raise ValueError("Okänd flow-metod; använd yolo eller two_pass.")
    if result <= 0:
        raise ValueError("Beräknad flow ratio måste vara större än noll.")
    return result


def calculate_pressure_advance(start, step, measured_height):
    """Pressure Advance represented by a measured height in Orca's tower."""
    start = _finite_number("Startvärde", start, minimum=0)
    step = _finite_number("Steg", step, positive=True)
    measured_height = _finite_number("Uppmätt höjd", measured_height, minimum=0)
    return start + step * measured_height


def calculate_max_volumetric_speed(start, step, measured_height,
                                   safety_margin_percent=0):
    """Measured Orca max-flow result and a user-selected safety margin."""
    start = _finite_number("Startflöde", start, minimum=0)
    step = _finite_number("Flödessteg", step, positive=True)
    measured_height = _finite_number("Uppmätt höjd", measured_height, minimum=0)
    margin = _finite_number("Säkerhetsmarginal", safety_margin_percent,
                            minimum=0, maximum=99)
    measured = start + step * measured_height
    return {
        "measured_mm3_s": measured,
        "recommended_mm3_s": measured * (1 - margin / 100),
        "safety_margin_percent": margin,
    }


def volumetric_speed_to_linear_speed(volumetric_speed, layer_height, line_width):
    """Convert mm³/s into the corresponding linear print speed in mm/s."""
    volumetric_speed = _finite_number("Volymflöde", volumetric_speed, positive=True)
    layer_height = _finite_number("Lagerhöjd", layer_height, positive=True)
    line_width = _finite_number("Linjebredd", line_width, positive=True)
    return volumetric_speed / layer_height / line_width


def tuning_calculation(kind, values):
    """Calculate one wizard result without allowing arbitrary function calls."""
    if not isinstance(values, dict):
        raise ValueError("Kalibreringsvärden saknas.")
    if kind == "rotation_distance":
        result = calculate_rotation_distance(
            values.get("current"), values.get("requested"), values.get("actual")
        )
        return {
            "value": result,
            "formatted": f"{result:.6f}",
            "profile_key": "rotation_distance",
            "destination": "Klipper printer.cfg → [extruder]",
        }
    if kind == "e_steps":
        result = calculate_e_steps(
            values.get("current"), values.get("requested"), values.get("actual")
        )
        return {
            "value": result,
            "formatted": f"{result:.3f}",
            "profile_key": "M92 E",
            "destination": "Marlin/RepRapFirmware",
        }
    if kind == "flow_ratio":
        result = calculate_flow_ratio(
            values.get("current"), values.get("modifier"), values.get("method", "yolo")
        )
        return {
            "value": result,
            "formatted": f"{result:.4f}",
            "profile_key": "filament_flow_ratio",
            "destination": "OrcaSlicer filamentprofil",
        }
    if kind == "pressure_advance":
        result = calculate_pressure_advance(
            values.get("start"), values.get("step"), values.get("height")
        )
        return {
            "value": result,
            "formatted": f"{result:.5f}",
            "profile_key": "pressure_advance",
            "destination": "OrcaSlicer filamentprofil",
        }
    if kind == "max_flow":
        result = calculate_max_volumetric_speed(
            values.get("start"), values.get("step"), values.get("height"),
            values.get("margin", 0),
        )
        return {
            **result,
            "value": result["recommended_mm3_s"],
            "formatted": f"{result['recommended_mm3_s']:.2f} mm³/s",
            "measured_formatted": f"{result['measured_mm3_s']:.2f} mm³/s",
            "profile_key": "filament_max_volumetric_speed",
            "destination": "OrcaSlicer filamentprofil",
        }
    raise ValueError("Okänd kalibreringsberäkning.")

SLICE_DATA_LOCK = threading.Lock()
LAST_SLICE_SNAPSHOT = None
SLICE_SNAPSHOTS_BY_PLATE = {}
OBSERVER_RUNTIME = {
    "plugin_loaded_at_epoch": int(time.time()),
    "execute_calls": 0,
    "last_execute_at_epoch": None,
    "last_step": None,
}

PAGE_HTML = r"""
<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Orca AI</title>
  <style>
    *{box-sizing:border-box} body{margin:0;color:var(--orca-fg);background:var(--orca-bg);font-family:var(--orca-font)}
    main{max-width:1220px;margin:auto;padding:22px} h1{margin:0;font-size:28px} h2{margin:0;font-size:17px}
    .muted{color:var(--orca-muted)} .intro{margin:7px 0 18px}
    .header,.panel-head,.composer,.row,.status{display:flex;align-items:center;gap:10px}
    .header,.panel-head{justify-content:space-between}
    .layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px}
    .panel,.card{border:1px solid var(--orca-border);border-radius:12px;background:color-mix(in srgb,var(--orca-bg) 94%,var(--orca-fg) 6%)}
    .panel{padding:17px}.section{margin-top:14px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px}
    .card{padding:11px;min-height:70px}.label{font-size:11px;color:var(--orca-muted);margin-bottom:5px}
    .value{font-weight:600;overflow-wrap:anywhere}.badge{padding:6px 10px;border:1px solid var(--orca-border);border-radius:999px}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#e29b32;margin-right:6px}
    .dot.ready{background:#32b768}.dot.busy{background:#3f8cff;animation:pulse 1s infinite}.dot.error{background:#d84a4a}
    @keyframes pulse{50%{opacity:.35}}
    .chat{height:480px;overflow-y:auto;margin:15px 0 12px;padding:6px 4px;display:flex;flex-direction:column;gap:12px}
    .message{max-width:92%;padding:11px 13px;border-radius:11px;white-space:pre-wrap;line-height:1.45;overflow-wrap:anywhere}
    .user{align-self:flex-end;background:var(--orca-accent);color:var(--orca-accent-fg)}
    .assistant{align-self:flex-start;background:var(--orca-bg);border:1px solid var(--orca-border);white-space:normal;width:min(100%,850px)}
    .assistant h1,.assistant h2,.assistant h3{line-height:1.25;margin:17px 0 7px}.assistant h1:first-child,.assistant h2:first-child,.assistant h3:first-child{margin-top:0}
    .assistant h1{font-size:20px}.assistant h2{font-size:17px}.assistant h3{font-size:15px}
    .assistant p{margin:7px 0}.assistant ul,.assistant ol{margin:7px 0;padding-left:23px}.assistant li{margin:4px 0}
    .assistant code{padding:1px 5px;border-radius:4px;background:color-mix(in srgb,var(--orca-bg) 85%,var(--orca-fg) 15%);font-family:monospace}
    .assistant pre{padding:10px;border:1px solid var(--orca-border);border-radius:7px;white-space:pre;overflow:auto}
    .assistant pre code{padding:0;background:transparent}.assistant blockquote{margin:9px 0;padding:3px 10px;border-left:3px solid var(--orca-accent);color:var(--orca-muted)}
    .table-wrap{max-width:100%;overflow-x:auto;margin:10px 0}.assistant table{width:100%;border-collapse:collapse;font-size:12px}
    .assistant th,.assistant td{padding:7px 8px;border:1px solid var(--orca-border);text-align:left;vertical-align:top;white-space:normal}
    .assistant th{background:color-mix(in srgb,var(--orca-bg) 82%,var(--orca-fg) 18%)}
    .error{align-self:flex-start;background:var(--orca-bg);border:1px solid #d84a4a;color:#d84a4a}
    .starter{margin:auto;text-align:center;max-width:560px}.starter h2{margin-bottom:8px}
    .quick{display:flex;flex-wrap:wrap;justify-content:center;gap:7px;margin-top:14px}
    .tabs{display:flex;gap:5px}.tabs button.active{background:var(--orca-accent);color:var(--orca-accent-fg);border-color:transparent}
    .hidden{display:none!important}.tune-top{margin:14px 0}.tune-card{padding:16px;border:1px solid var(--orca-border);border-radius:11px;background:var(--orca-bg);min-height:340px}
    .tune-meta{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 13px}.tune-pill{font-size:11px;padding:4px 8px;border-radius:999px;border:1px solid var(--orca-border);color:var(--orca-muted)}
    .tune-card h3{margin:0 0 8px;font-size:18px}.tune-card p{line-height:1.45}.tune-card ul,.tune-card ol{padding-left:22px;line-height:1.45}
    .tune-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:13px 0}.tune-fields .field{margin:0}
    .command{padding:10px;border:1px solid var(--orca-border);border-radius:7px;background:color-mix(in srgb,var(--orca-bg) 82%,var(--orca-fg) 18%);font-family:monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0}
    .tune-result{margin-top:12px;padding:11px;border-left:3px solid var(--orca-accent);background:color-mix(in srgb,var(--orca-bg) 88%,var(--orca-accent) 12%)}
    .progress-track{height:7px;border-radius:999px;background:color-mix(in srgb,var(--orca-bg) 80%,var(--orca-fg) 20%);overflow:hidden}.progress-fill{height:100%;background:var(--orca-accent);transition:width .2s}
    button{border:0;border-radius:8px;padding:9px 13px;cursor:pointer;font-weight:600;background:var(--orca-accent);color:var(--orca-accent-fg)}
    button.secondary{background:transparent;color:var(--orca-fg);border:1px solid var(--orca-border)}
    button:disabled{opacity:.5;cursor:default}
    textarea,input,select{border:1px solid var(--orca-border);border-radius:8px;padding:10px 11px;background:var(--orca-bg);color:var(--orca-fg);font-family:inherit}
    textarea{flex:1;min-width:0;min-height:48px;max-height:130px;resize:vertical}.composer{align-items:flex-end}.composer button{min-height:48px}
    input,select{width:100%}.field{margin-top:10px}.field label{display:block;font-size:11px;color:var(--orca-muted);margin-bottom:5px}
    .small{font-size:12px;line-height:1.4}.privacy{font-size:12px;line-height:1.45}details{margin-top:11px}summary{cursor:pointer;color:var(--orca-muted)}
    pre{max-height:230px;overflow:auto;font-size:11px;white-space:pre-wrap}
    @media(max-width:850px){.layout{grid-template-columns:1fr}.chat{height:390px}}
  </style>
</head>
<body>
<main>
  <div class="header">
    <div><h1>Orca AI</h1><div class="intro muted">Projektmedveten rådgivning – ändrar inget automatiskt.</div></div>
    <div class="badge"><span class="dot" id="status-dot"></span><span id="status">Startar…</span></div>
  </div>
  <div class="layout">
    <section class="panel">
      <div class="panel-head">
        <div class="tabs"><button class="secondary active" id="tab-chat">Chatt</button><button class="secondary" id="tab-tuning">Tuning</button></div>
        <button class="secondary" id="clear">Rensa</button>
      </div>
      <div id="chat-view">
        <div class="row" style="margin-top:10px">
          <div class="field" style="margin:0;flex:1"><label>Erfarenhetsnivå</label><select id="experience-level"><option value="beginner">Nybörjare</option><option value="experienced" selected>Erfaren</option><option value="expert">Expert</option></select></div>
          <div class="field" style="margin:0;flex:1"><label>Svarsläge</label><select id="response-mode"><option value="quick" selected>Snabbkontroll</option><option value="deep">Djup analys</option></select></div>
        </div>
        <div class="chat" id="chat">
          <div class="starter" id="starter">
            <h2>Vad vill du förbättra?</h2>
            <div class="muted">Aktiv skrivare, filament, process och modell används som kontext.</div>
            <div class="quick">
              <button class="secondary">Kontrollera projektet före utskrift</button>
              <button class="secondary">Optimera för hållfasthet</button>
              <button class="secondary">Kan utskriftstiden kortas?</button>
              <button class="secondary">Behöver modellen support?</button>
            </div>
          </div>
        </div>
        <div class="composer"><textarea id="prompt" placeholder="Fråga om modellen eller inställningarna…"></textarea><button id="send">Skicka</button></div>
        <div class="small muted" style="margin-top:7px">Enter skickar · Shift+Enter gör ny rad</div>
      </div>
      <div id="tuning-view" class="hidden">
        <div class="tune-top">
          <div class="row"><div style="flex:1"><strong>Ellis-inspirerad fullkalibrering</strong><div class="small muted" id="tune-summary">Läser aktiv profil…</div></div><button class="secondary" id="tune-reset">Börja om</button></div>
          <div class="progress-track" style="margin-top:10px"><div class="progress-fill" id="tune-progress"></div></div>
          <div class="field"><label>Kalibreringssteg</label><select id="tune-step"></select></div>
        </div>
        <div class="tune-card" id="tune-card"></div>
        <div class="row" style="justify-content:space-between;margin-top:11px"><button class="secondary" id="tune-prev">Föregående</button><div class="row"><button class="secondary" id="tune-skip">Hoppa över</button><button id="tune-done">Markera klar</button></div><button class="secondary" id="tune-next">Nästa</button></div>
      </div>
    </section>
    <aside>
      <section class="panel">
        <div class="panel-head"><h2>Aktuellt projekt</h2><button class="secondary" id="refresh">Uppdatera</button></div>
        <div class="cards">
          <div class="card"><div class="label">Skrivare</div><div class="value" id="printer">Läser…</div></div>
          <div class="card"><div class="label">Process</div><div class="value" id="process">Läser…</div></div>
          <div class="card"><div class="label">Filament</div><div class="value" id="filaments">Läser…</div></div>
          <div class="card"><div class="label">Hela projektet</div><div class="value" id="model">Läser…</div></div>
        </div>
        <div class="field"><label>Antal byggplattor (anges manuellt)</label><input id="plate-count" type="number" min="1" step="1" placeholder="Okänt"></div>
        <div class="small muted" style="margin-top:6px">Orca 2.5-dev visar aktiv platta men plugin-API:t lämnar ännu inte objektens plattillhörighet.</div>
        <div class="card" style="margin-top:10px;min-height:0"><div class="label">Slicing-observatör</div><div class="value small" id="slice-info">Kontrollerar…</div></div>
        <div class="small muted" style="margin-top:6px">Aktivera via Process-inställningarnas sökfält: <strong>Slicing Pipeline Plugin</strong> → <strong>Orca AI Slice Observer</strong>. Skiva sedan en platta och tryck Uppdatera.</div>
        <details><summary>Visa data som skickas</summary><pre id="context">Läser…</pre></details>
      </section>
      <section class="panel section">
        <h2>OpenAI API</h2>
        <p class="small muted">Nyckeln hålls endast i minnet tills OrcaSlicer stängs.</p>
        <div class="field"><label>API-nyckel</label><input id="key" type="password" autocomplete="off" placeholder="sk-…"></div>
        <div class="field"><label>Modell</label><input id="model-name" value="gpt-5.6-terra" spellcheck="false"></div>
        <div class="row" style="margin-top:10px"><button id="save">Använd denna session</button></div>
        <div class="status small" style="margin-top:10px"><span class="dot" id="key-dot"></span><span id="key-status">Ingen nyckel</span></div>
      </section>
      <section class="panel section privacy"><strong>Integritet</strong><br>När du skickar överförs frågan och den visade sammanfattningen till OpenAI. STL/3MF-filen och meshgeometrin skickas inte.</section>
    </aside>
  </div>
</main>
<script>
const $=id=>document.getElementById(id);let busy=false,currentContext=null,tuneState={index:0,done:[],skipped:[]};
const TUNING_STEPS=[
  {id:"preflight",title:"1. Mekanisk grundkontroll",scope:"Skrivare"},
  {id:"pid",title:"2. PID – hotend och bädd",scope:"Skrivare · vid behov"},
  {id:"extruder",title:"3. Extruderkalibrering",scope:"Skrivare"},
  {id:"first_layer",title:"4. Byggyta och första lager",scope:"Skrivare"},
  {id:"input_shaper",title:"5. Input Shaper",scope:"Skrivare · Klipper"},
  {id:"temperature",title:"6. Temperatur",scope:"Filament"},
  {id:"pa",title:"7. Pressure Advance",scope:"Filament"},
  {id:"flow",title:"8. Flow Ratio",scope:"Filament"},
  {id:"cooling",title:"9. Kylning och lagertid",scope:"Filament"},
  {id:"retraction",title:"10. Retraction",scope:"Filament"},
  {id:"max_flow",title:"11. Maxvolymflöde",scope:"Filament · prestanda"}
];
function status(text,state=""){ $("status").textContent=text;$("status-dot").className="dot "+state }
function setBusy(v){busy=v;$("send").disabled=v;$("prompt").disabled=v;status(v?"AI tänker…":"Redo",v?"busy":"ready")}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function inlineMd(s){let x=escapeHtml(s);x=x.replace(/`([^`]+)`/g,"<code>$1</code>");x=x.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");x=x.replace(/__([^_]+)__/g,"<strong>$1</strong>");return x}
function tableCells(line){let x=line.trim();if(x.startsWith("|"))x=x.slice(1);if(x.endsWith("|"))x=x.slice(0,-1);return x.split("|").map(v=>v.trim())}
function tableDivider(line){return tableCells(line).length>0&&tableCells(line).every(v=>/^:?-{3,}:?$/.test(v))}
function renderMarkdown(text){
  const lines=String(text||"").replace(/\r/g,"").split("\n");let out="",i=0,list="";
  const closeList=()=>{if(list){out+="</"+list+">";list=""}};
  while(i<lines.length){const line=lines[i];
    if(/^```/.test(line.trim())){closeList();const code=[];i++;while(i<lines.length&&!/^```/.test(lines[i].trim()))code.push(lines[i++]);if(i<lines.length)i++;out+="<pre><code>"+escapeHtml(code.join("\n"))+"</code></pre>";continue}
    const heading=line.match(/^(#{1,3})\s+(.+)$/);if(heading){closeList();const n=heading[1].length;out+="<h"+n+">"+inlineMd(heading[2])+"</h"+n+">";i++;continue}
    if(line.includes("|")&&i+1<lines.length&&tableDivider(lines[i+1])){closeList();const head=tableCells(line);i+=2;const rows=[];while(i<lines.length&&lines[i].includes("|")&&lines[i].trim()){rows.push(tableCells(lines[i++]));}out+='<div class="table-wrap"><table><thead><tr>'+head.map(c=>"<th>"+inlineMd(c)+"</th>").join("")+"</tr></thead><tbody>"+rows.map(r=>"<tr>"+head.map((_,j)=>"<td>"+inlineMd(r[j]||"")+"</td>").join("")+"</tr>").join("")+"</tbody></table></div>";continue}
    const bullet=line.match(/^\s*[-*+]\s+(.+)$/),numbered=line.match(/^\s*\d+[.)]\s+(.+)$/);
    if(bullet||numbered){const wanted=bullet?"ul":"ol";if(list!==wanted){closeList();list=wanted;out+="<"+list+">"}out+="<li>"+inlineMd((bullet||numbered)[1])+"</li>";i++;continue}
    closeList();if(!line.trim()){i++;continue}if(/^>\s?/.test(line)){out+="<blockquote>"+inlineMd(line.replace(/^>\s?/,""))+"</blockquote>"}else{out+="<p>"+inlineMd(line)+"</p>"}i++;
  }
  closeList();return out
}
function plateCount(){const n=Number($("plate-count").value);return Number.isInteger(n)&&n>0?n:null}
function firstValue(v,fallback){if(Array.isArray(v))v=v[0];if(v===null||v===undefined||v==="")return fallback;const n=Number(v);return Number.isFinite(n)?n:fallback}
function filamentValues(){return currentContext?.settings?.filaments?.[0]?.values||{}}
function tuningStorageKey(){return "orca-ai-tuning:"+(currentContext?.printer||"printer")+":"+(currentContext?.filaments?.[0]||"filament")}
function loadTuneState(){tuneState={index:0,done:[],skipped:[]};try{const saved=JSON.parse(localStorage.getItem(tuningStorageKey())||"null");if(saved&&Number.isInteger(saved.index))tuneState={index:Math.max(0,Math.min(TUNING_STEPS.length-1,saved.index)),done:Array.isArray(saved.done)?saved.done:[],skipped:Array.isArray(saved.skipped)?saved.skipped:[]}}catch(e){}renderTuning()}
function saveTuneState(){try{localStorage.setItem(tuningStorageKey(),JSON.stringify(tuneState))}catch(e){}}
function tuneField(id,label,value,extra=""){return '<div class="field"><label>'+escapeHtml(label)+'</label><input id="'+id+'" value="'+escapeHtml(value)+'" '+extra+'></div>'}
function tuneSelect(id,label,options){return '<div class="field"><label>'+escapeHtml(label)+'</label><select id="'+id+'">'+options.map(o=>'<option value="'+o[0]+'">'+escapeHtml(o[1])+'</option>').join("")+'</select></div>'}
function tuningStepHtml(step){const f=filamentValues(),nozzle=firstValue(f.nozzle_temperature,240),bed=firstValue(f.hot_plate_temp,100),flow=firstValue(f.filament_flow_ratio,0.98),maxFlow=firstValue(f.filament_max_volumetric_speed,20),pa=firstValue(f.pressure_advance,0);
  if(step.id==="preflight")return '<h3>Mekaniken först</h3><p>Kalibrering kan inte kompensera för ett mekaniskt fel. Kontrollera detta innan du börjar skriva testdelar:</p><ul><li>Remspänning och att rörelsen är jämn utan glapp eller kärvning.</li><li>Skruvar, linjärskena, trissor och särskilt extruderns grub screws.</li><li>Ren och korrekt varmåtdragen nozzle utan läckage.</li><li>Filamentet extruderar rakt ned utan sidoböjning eller tecken på delvis stopp.</li><li>Rätt termistortyper och rimliga temperaturvärden i Klipper.</li></ul>';
  if(step.id==="pid")return '<h3>PID-tuning</h3><p>Gör detta efter byte av hotend, heater, termistor, bädd eller när temperaturen oscillerar. Det behöver normalt inte upprepas för varje filament.</p><div class="tune-fields">'+tuneField("pid-hotend","Hotendmål °C",nozzle,'type="number"')+tuneField("pid-bed","Bäddmål °C",bed,'type="number"')+'</div><p class="small muted">Kör ett test i taget när skrivaren är tom och stilla. Klipper startar om när du kör SAVE_CONFIG.</p><div class="label">Hotend</div><div class="command" id="pid-hotend-command"></div><div class="label">Bädd</div><div class="command" id="pid-bed-command"></div>';
  if(step.id==="extruder")return '<h3>Extruderkalibrering</h3><p>Mät faktisk filamentrörelse. För en direktdriven Voron kan testet göras varmt, men upprepa det och kräv konsekventa resultat.</p><div class="tune-fields">'+tuneSelect("extruder-firmware","Firmware",[["rotation_distance","Klipper"],["e_steps","Marlin / RepRapFirmware"]])+tuneField("extruder-current","Nuvarande värde",'','type="number" step="any" placeholder="Läs från printer.cfg"')+tuneField("extruder-requested","Begärd extrudering mm",100,'type="number" step="any"')+tuneField("extruder-actual","Faktiskt extruderat mm",100,'type="number" step="any"')+'</div><button id="calc-extruder">Beräkna</button><div id="tune-result" class="tune-result hidden"></div>';
  if(step.id==="first_layer")return '<h3>Byggyta och första lager</h3><ol><li>Rengör byggytan och gör en grov Z-/endstop-kalibrering.</li><li>Skriv flera ett-lagersfält över bädden med minst 0,25 mm första lager.</li><li>Justera live tills linjerna sitter ihop utan tydliga åsar eller genomskinliga glipor.</li><li>Spara den slutliga Z-justeringen enligt din endstop-/probe-konfiguration.</li></ol><p class="small muted">Detta är ett manuellt kvalitetssteg. Assistenten ska inte gissa Z-offset från slicerdata.</p>';
  if(step.id==="input_shaper")return '<h3>Input Shaper</h3><p>Om en accelerometer är konfigurerad i Klipper kan du mäta båda axlarna automatiskt:</p><div class="command">SHAPER_CALIBRATE\nSAVE_CONFIG</div><p>Kontrollera konsolens rekommenderade shaper och smoothing innan du sparar. Hoppa över steget om skrivaren saknar accelerometer; manuell ringingtower kommer senare.</p>';
  if(step.id==="temperature")return '<h3>Temperatur</h3><p>Välj <strong>Calibration → Temperature</strong> i Orca och generera ett torn för det aktiva materialet.</p><ul><li>Bedöm lagerbindning, överhäng, bridging, stringing och ytfinish tillsammans.</li><li>Välj inte en temperatur enbart för att en nivå ser blankast ut.</li><li>Spara vald nozzle- och bäddtemperatur i filamentprofilen innan PA och Flow Ratio.</li></ul><div class="tune-result"><strong>Aktuell profil:</strong> nozzle '+nozzle+' °C · bädd '+bed+' °C</div>';
  if(step.id==="pa")return '<h3>Pressure Advance</h3><p>Välj <strong>Calibration → Pressure Advance → Pattern</strong> och Direct Drive för din Voron. Leta efter skarpast hörn med minst bulge, grop och glipa.</p><div class="tune-fields">'+tuneField("pa-start","Startvärde",0,'type="number" step="any"')+tuneField("pa-step","Steg per mm",0.002,'type="number" step="any"')+tuneField("pa-height","Vald höjd mm",8,'type="number" step="any"')+tuneField("pa-current","Nuvarande PA",pa,'type="number" step="any" disabled')+'</div><button id="calc-pa">Beräkna</button><div id="tune-result" class="tune-result hidden"></div>';
  if(step.id==="flow")return '<h3>Flow Ratio</h3><p>Välj <strong>Calibration → Flow Ratio → YOLO</strong>. Bedöm den breda mittdelen: jämn yta, inga öppna spår och så lite materialansamling som möjligt.</p><div class="tune-fields">'+tuneSelect("flow-method","Metod",[["yolo","Archimedean Chords + YOLO"],["two_pass","Äldre tvåpassmetod"]])+tuneField("flow-current","Nuvarande flow ratio",flow,'type="number" step="any"')+tuneField("flow-modifier","Vinnande modifierare",0.01,'type="number" step="any"')+'</div><button id="calc-flow">Beräkna</button><div id="tune-result" class="tune-result hidden"></div>';
  if(step.id==="cooling")return '<h3>Kylning och lagertid</h3><p>Verifiera kylningen med verkliga små lager och överhäng. Bedöm materialet i den kammartemperatur du normalt använder.</p><ul><li>Öka inte fläkten för att maskera för hög temperatur eller för kort lagertid.</li><li>För ABS: prioritera lagerbindning och warpingmotstånd, och använd högre kylning endast där geometrin kräver det.</li><li>Spara resultatet i filamentprofilen, inte i en enskild process om det är materialberoende.</li></ul>';
  if(step.id==="retraction")return '<h3>Retraction</h3><p>Kör Orcas retraction-test först efter PA och Flow Ratio. Börja lågt på en direktdriven extruder och höj tills stringing förbättras utan att skapa hål, slipning eller onödiga retraktioner.</p><p class="small muted">Kontrollera även temperatur och fukt innan ett högt retractionvärde accepteras. Stringing är inte alltid ett retractionproblem.</p>';
  if(step.id==="max_flow")return '<h3>Maxvolymflöde</h3><p>Välj <strong>Calibration → Max Volumetric Speed</strong>. Mät höjden precis innan glansförändring, underextrudering eller försämrad lagerbindning börjar.</p><div class="tune-fields">'+tuneField("mf-start","Start mm³/s",5,'type="number" step="any"')+tuneField("mf-step","Steg per mm",0.5,'type="number" step="any"')+tuneField("mf-height","Uppmätt höjd mm",19,'type="number" step="any"')+tuneField("mf-margin","Säkerhetsmarginal %",15,'type="number" step="any"')+'</div><button id="calc-max-flow">Beräkna</button><div id="tune-result" class="tune-result hidden"></div><p class="small muted">Aktuell profilgräns: '+maxFlow+' mm³/s. Testet är ett best case; marginalen är ett separat beslut.</p>';
  return "";
}
function updatePidCommands(){if(!$("pid-hotend-command"))return;const h=Number($("pid-hotend").value),b=Number($("pid-bed").value);$("pid-hotend-command").textContent=Number.isFinite(h)&&h>0?'PID_CALIBRATE HEATER=extruder TARGET='+h+'\nSAVE_CONFIG':'Ange en giltig hotendtemperatur.';$("pid-bed-command").textContent=Number.isFinite(b)&&b>0?'PID_CALIBRATE HEATER=heater_bed TARGET='+b+'\nSAVE_CONFIG':'Ange en giltig bäddtemperatur.'}
function renderTuning(){if(!$("tune-card"))return;const step=TUNING_STEPS[tuneState.index];$("tune-step").innerHTML=TUNING_STEPS.map((s,i)=>'<option value="'+i+'" '+(i===tuneState.index?'selected':'')+'>'+escapeHtml(s.title)+(tuneState.done.includes(s.id)?' ✓':(tuneState.skipped.includes(s.id)?' – hoppad':''))+'</option>').join("");$("tune-card").innerHTML='<div class="tune-meta"><span class="tune-pill">'+escapeHtml(step.scope)+'</span><span class="tune-pill">Steg '+(tuneState.index+1)+' av '+TUNING_STEPS.length+'</span></div>'+tuningStepHtml(step);const completed=new Set([...tuneState.done,...tuneState.skipped]).size;$("tune-progress").style.width=(completed/TUNING_STEPS.length*100)+'%';$("tune-prev").disabled=tuneState.index===0;$("tune-next").disabled=tuneState.index===TUNING_STEPS.length-1;bindTuningActions();updatePidCommands()}
function bindTuningActions(){["pid-hotend","pid-bed"].forEach(id=>{if($(id))$(id).oninput=updatePidCommands});if($("calc-extruder"))$("calc-extruder").onclick=()=>tuneCalculate($("extruder-firmware").value,{current:$("extruder-current").value,requested:$("extruder-requested").value,actual:$("extruder-actual").value});if($("calc-pa"))$("calc-pa").onclick=()=>tuneCalculate("pressure_advance",{start:$("pa-start").value,step:$("pa-step").value,height:$("pa-height").value});if($("calc-flow"))$("calc-flow").onclick=()=>tuneCalculate("flow_ratio",{current:$("flow-current").value,modifier:$("flow-modifier").value,method:$("flow-method").value});if($("calc-max-flow"))$("calc-max-flow").onclick=()=>tuneCalculate("max_flow",{start:$("mf-start").value,step:$("mf-step").value,height:$("mf-height").value,margin:$("mf-margin").value})}
function tuneCalculate(calculation,values){window.orca.postMessage({type:"tuning_calculate",calculation,values})}
function showTuningResult(result){const e=$("tune-result");if(!e)return;e.classList.remove("hidden");let extra=result.measured_formatted?'<div class="small muted">Uppmätt gräns: '+escapeHtml(result.measured_formatted)+'</div>':'';e.innerHTML='<strong>'+escapeHtml(result.profile_key)+': '+escapeHtml(result.formatted)+'</strong><div class="small">Skrivs manuellt i '+escapeHtml(result.destination)+'.</div>'+extra}
function showTuningError(message){const e=$("tune-result");if(!e)return;e.classList.remove("hidden");e.innerHTML='<strong>Kontrollera värdena</strong><div class="small">'+escapeHtml(message)+'</div>'}
function updateTuningContext(){if(!currentContext)return;const nozzle=firstValue(currentContext.settings?.printer?.nozzle_diameter,0.4);$("tune-summary").textContent=(currentContext.printer||"Okänd skrivare")+' · '+nozzle+' mm · '+((currentContext.filaments||[]).join(", ")||"okänt filament");loadTuneState()}
function switchView(view){const tuning=view==="tuning";$("chat-view").classList.toggle("hidden",tuning);$("tuning-view").classList.toggle("hidden",!tuning);$("tab-chat").classList.toggle("active",!tuning);$("tab-tuning").classList.toggle("active",tuning);$("clear").classList.toggle("hidden",tuning);if(tuning)renderTuning()}
function add(role,text){const s=$("starter");if(s)s.remove();const e=document.createElement("div");e.className="message "+role;if(role==="assistant")e.innerHTML=renderMarkdown(text);else e.textContent=text;$("chat").appendChild(e);$("chat").scrollTop=$("chat").scrollHeight}
function getContext(){status("Läser projekt","busy");window.orca.postMessage({type:"context",plate_count:plateCount()})}
function send(text){const q=String(text||"").trim();if(!q||busy)return;add("user",q);$("prompt").value="";setBusy(true);window.orca.postMessage({type:"chat",text:q,plate_count:plateCount(),experience_level:$("experience-level").value,response_mode:$("response-mode").value})}
window.orca.onMessage(m=>{
  if(!m||!m.type)return;
  if(m.type==="context"){const c=m.payload;currentContext=c;$("printer").textContent=c.printer;$("process").textContent=c.process;$("filaments").textContent=c.filaments.join(", ")||"Inga";const z=c.model.project_extent_mm;$("model").textContent=c.model.object_count+" objekt · "+c.model.instance_count+" instanser"+(z?" · "+z.map(v=>Number(v).toFixed(1)).join(" × ")+" mm totalt":"");const s=c.slicing||{},snap=s.last_snapshot,n=Number(s.captured_plate_count||0);if(snap&&snap.error)$("slice-info").textContent="Kördes, men analysen misslyckades: "+snap.error;else if(snap)$("slice-info").textContent=(n>1?n+" plattor fångade":"Snapshot fångad")+" · senast "+(snap.plate_index_1_based?"platta "+snap.plate_index_1_based+" · ":"")+snap.object_count+" objekt · "+snap.plate_layer_count+" lager";else if(s.observer_status==="not_selected")$("slice-info").textContent="Inte vald i den aktiva processprofilen";else if(s.observer_status==="selected_waiting")$("slice-info").textContent="Vald · väntar på ny slicing efter pluginstart";else if(s.observer_status==="ran_without_snapshot")$("slice-info").textContent="Kördes, men inget snapshot skapades · se diagnostik";else $("slice-info").textContent="Kan inte läsa valet i den aktiva processprofilen";$("context").textContent=JSON.stringify(c,null,2);updateTuningContext();if(!busy)status("Redo","ready")}
  if(m.type==="session"){ $("model-name").value=m.model;const bad=Boolean(m.key_problem);$("key-status").textContent=bad?"API-nyckeln innehåller ogiltiga tecken":(m.key_configured?"API-nyckel aktiv ("+m.key_source+")":"Ingen nyckel konfigurerad");$("key-dot").className="dot "+(bad?"error":(m.key_configured?"ready":""));$("key").value=""}
  if(m.type==="answer"){setBusy(false);add("assistant",m.text)}
  if(m.type==="tuning_result"){showTuningResult(m.payload)}
  if(m.type==="tuning_error"){showTuningError(m.message)}
  if(m.type==="error"){setBusy(false);add("error",m.message)}
  if(m.type==="cleared"){$("chat").innerHTML='<div class="starter" id="starter"><h2>Ny konversation</h2><div class="muted">Projektkontexten läses om vid varje fråga.</div></div>'}
});
$("send").onclick=()=>send($("prompt").value);
$("prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send(e.target.value)}};
document.querySelectorAll(".quick button").forEach(b=>b.onclick=()=>send(b.textContent));
$("refresh").onclick=getContext;$("plate-count").onchange=getContext;$("clear").onclick=()=>window.orca.postMessage({type:"clear"});
$("save").onclick=()=>window.orca.postMessage({type:"session",api_key:$("key").value,model:$("model-name").value});
$("tab-chat").onclick=()=>switchView("chat");$("tab-tuning").onclick=()=>switchView("tuning");
$("tune-step").onchange=e=>{tuneState.index=Number(e.target.value);saveTuneState();renderTuning()};
$("tune-prev").onclick=()=>{tuneState.index=Math.max(0,tuneState.index-1);saveTuneState();renderTuning()};
$("tune-next").onclick=()=>{tuneState.index=Math.min(TUNING_STEPS.length-1,tuneState.index+1);saveTuneState();renderTuning()};
$("tune-done").onclick=()=>{const id=TUNING_STEPS[tuneState.index].id;tuneState.done=[...new Set([...tuneState.done,id])];tuneState.skipped=tuneState.skipped.filter(x=>x!==id);if(tuneState.index<TUNING_STEPS.length-1)tuneState.index++;saveTuneState();renderTuning()};
$("tune-skip").onclick=()=>{const id=TUNING_STEPS[tuneState.index].id;tuneState.skipped=[...new Set([...tuneState.skipped,id])];tuneState.done=tuneState.done.filter(x=>x!==id);if(tuneState.index<TUNING_STEPS.length-1)tuneState.index++;saveTuneState();renderTuning()};
$("tune-reset").onclick=()=>{tuneState={index:0,done:[],skipped:[]};saveTuneState();renderTuning()};
window.orca.postMessage({type:"session_status"});getContext();
</script>
</body>
</html>
"""

PROCESS_KEYS = (
    "layer_height", "initial_layer_print_height", "wall_loops",
    "outer_wall_line_width", "inner_wall_line_width", "top_surface_line_width",
    "sparse_infill_line_width",
    "top_shell_layers", "bottom_shell_layers", "sparse_infill_density",
    "sparse_infill_pattern", "internal_solid_infill_pattern", "enable_support",
    "support_type", "support_threshold_angle", "support_on_build_plate_only",
    "brim_type", "brim_width", "initial_layer_speed", "outer_wall_speed",
    "inner_wall_speed", "sparse_infill_speed", "top_surface_speed", "travel_speed",
    "default_acceleration", "outer_wall_acceleration", "inner_wall_acceleration",
    "initial_layer_acceleration", "seam_position",
    "wall_generator", "detect_thin_wall", "ironing_type", "print_sequence",
    "slicing_pipeline_plugin",
)
PRINTER_KEYS = (
    "printer_model", "nozzle_diameter", "printable_area", "bed_exclude_area",
    "printable_height",
    "extruder_clearance_radius", "machine_max_speed_x", "machine_max_speed_y",
    "machine_max_speed_z", "machine_max_acceleration_x", "machine_max_acceleration_y",
)
FILAMENT_KEYS = (
    "filament_type", "filament_vendor", "filament_diameter",
    "filament_flow_ratio", "enable_pressure_advance", "pressure_advance",
    "pressure_advance_smooth_time", "nozzle_temperature",
    "nozzle_temperature_initial_layer", "hot_plate_temp",
    "hot_plate_temp_initial_layer", "chamber_temperature",
    "filament_max_volumetric_speed", "fan_max_speed", "fan_min_speed",
    "initial_layer_fan_speed", "close_fan_the_first_x_layers",
    "full_fan_speed_layer", "fan_cooling_layer_time", "slow_down_layer_time",
    "slow_down_for_layer_cooling", "enable_overhang_bridge_fan",
    "overhang_fan_speed", "filament_retraction_length",
)


def _xyz(values):
    return [round(float(v), 2) for v in values]


def _rotation_degrees(values):
    return [round(math.degrees(float(v)), 2) for v in values]


def _instance_context(instance):
    box = instance.bounding_box()
    return {
        "id": int(instance.id()),
        "printable": bool(instance.is_printable()),
        "offset_mm": _xyz(instance.offset()),
        "rotation_deg": _rotation_degrees(instance.rotation()),
        "scale": _xyz(instance.scaling_factor()),
        "mirror": _xyz(instance.mirror()),
        "world_bbox_mm": ({
            "min": _xyz(box.min),
            "max": _xyz(box.max),
            "size": _xyz(box.size),
        } if box.defined else None),
        "plate_membership": "unavailable",
    }


def _json_value(value):
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _name(preset):
    return str(getattr(preset, "name", "") or "Ingen vald")


def _config(preset, keys):
    result = {}
    for key in keys:
        try:
            value = preset.config_value(key)
        except Exception:
            value = None
        if value is not None:
            result[key] = _json_value(value)
    return result


def _observer_selected(value):
    """Match both the friendly name and Orca's resolved name;uuid;capability form."""
    if value is None:
        return None
    values = value if isinstance(value, (tuple, list)) else [value]
    return any("orca ai slice observer" in str(item).lower() for item in values)


def _number(value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return round(float(match.group()), 2) if match else None


def _printable_area(value):
    points = []
    for x, y in re.findall(r"(-?\d+(?:\.\d+)?)x(-?\d+(?:\.\d+)?)", str(value or "")):
        points.append([round(float(x), 2), round(float(y), 2)])
    if len(points) < 3:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return {
        "polygon_mm": points,
        "bounding_size_mm": [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)],
    }


def _reported_plate_count(value):
    try:
        count = int(value)
        return count if count > 0 else None
    except (TypeError, ValueError):
        return None


def _line_width(value, nozzle):
    number = _number(value)
    if number is None:
        return None, None
    if "%" in str(value):
        return (round(nozzle * number / 100, 3), "percent_of_nozzle") if nozzle else (None, None)
    if number <= 0:
        return (nozzle, "automatic_approximated_as_nozzle") if nozzle else (None, None)
    return number, "profile_value"


def _flow_estimates(process_values, printer_values, filament_values):
    layer = _number(process_values.get("layer_height"))
    nozzle = _number(printer_values.get("nozzle_diameter"))
    if not layer:
        return None
    features = (
        ("outer_wall", "outer_wall_speed", "outer_wall_line_width"),
        ("inner_wall", "inner_wall_speed", "inner_wall_line_width"),
        ("top_surface", "top_surface_speed", "top_surface_line_width"),
        ("sparse_infill", "sparse_infill_speed", "sparse_infill_line_width"),
    )
    estimates = {}
    for name, speed_key, width_key in features:
        speed = _number(process_values.get(speed_key))
        width, source = _line_width(process_values.get(width_key), nozzle)
        if speed is not None and width is not None:
            estimates[name] = {
                "nominal_mm3_s": round(layer * width * speed, 2),
                "speed_mm_s": speed,
                "line_width_mm": width,
                "line_width_source": source,
            }
    limits = [_number(f.get("filament_max_volumetric_speed")) for f in filament_values]
    limits = [value for value in limits if value is not None]
    return {
        "method": "approximate rectangular bead: layer_height × line_width × requested_speed",
        "warning": "Requested speed is not necessarily reached; acceleration, path length and slicer volumetric limiting also apply.",
        "filament_limits_mm3_s": limits,
        "features": estimates,
    }


def collect_context(plate_count=None):
    bundle = orca.host.preset_bundle()
    model = orca.host.model()
    process = bundle.current_process_preset()
    printer = bundle.current_printer_preset()
    filaments = [p for p in bundle.current_filament_presets() if p is not None]
    process_values = _config(process, PROCESS_KEYS)
    printer_values = _config(printer, PRINTER_KEYS)
    filament_entries = [{"name": _name(p), "values": _config(p, FILAMENT_KEYS)} for p in filaments]
    filament_values = [entry["values"] for entry in filament_entries]
    build_area = _printable_area(printer_values.get("printable_area"))
    build_volume = {
        "source": "active_printer_profile",
        "bed": build_area,
        "height_mm": _number(printer_values.get("printable_height")),
    }
    objects = []
    errors = 0
    instance_count = 0
    for obj in model.objects():
        try:
            box = obj.raw_mesh_bounding_box()
        except Exception:
            box = obj.bounding_box()
        mesh_errors = int(obj.mesh_errors_count())
        errors += mesh_errors
        instance_count += int(obj.instance_count())
        instances = []
        try:
            instances = [_instance_context(instance) for instance in obj.instances()]
        except Exception:
            pass
        objects.append({
            "id": int(obj.id()),
            "name": str(obj.name or "Namnlöst objekt"),
            "intrinsic_size_mm": _xyz(box.size) if box.defined else None,
            "instance_count": int(obj.instance_count()),
            "facets": int(obj.facets_count()),
            "mesh_errors": mesh_errors,
            "support_painted": bool(obj.is_fdm_support_painted()),
            "seam_painted": bool(obj.is_seam_painted()),
            "instances": instances,
        })
    box = model.bounding_box()
    try:
        current_plate = int(model.current_plate_index()) + 1
    except Exception:
        current_plate = None
    observer_selected = _observer_selected(process_values.get("slicing_pipeline_plugin"))
    with SLICE_DATA_LOCK:
        slice_snapshot = (json.loads(json.dumps(LAST_SLICE_SNAPSHOT, ensure_ascii=False))
                          if LAST_SLICE_SNAPSHOT is not None else None)
        plate_snapshots = json.loads(json.dumps(
            [SLICE_SNAPSHOTS_BY_PLATE[key] for key in sorted(SLICE_SNAPSHOTS_BY_PLATE)],
            ensure_ascii=False,
        ))
        observer_runtime = dict(OBSERVER_RUNTIME)
    if slice_snapshot is not None:
        observer_status = "captured"
    elif observer_runtime["execute_calls"]:
        observer_status = "ran_without_snapshot"
    elif observer_selected is True:
        observer_status = "selected_waiting"
    elif observer_selected is False:
        observer_status = "not_selected"
    else:
        observer_status = "selection_unavailable"
    reported_count = _reported_plate_count(plate_count)
    captured_plate_numbers = [snapshot.get("plate_index_1_based") for snapshot in plate_snapshots]
    captured_plate_numbers = [number for number in captured_plate_numbers if isinstance(number, int)]
    complete_for_reported_project = (
        reported_count is not None
        and set(captured_plate_numbers) == set(range(1, reported_count + 1))
    )
    return {
        "printer": _name(printer),
        "process": _name(process),
        "filaments": [str(n) for n in bundle.current_filament_preset_names()],
        "plates": {
            "reported_count": reported_count,
            "active_plate_1_based": current_plate,
            "object_membership_available": False,
            "scope_note": "Objektdata och projektutbredning gäller hela projektet över alla byggplattor; objektens plattillhörighet exponeras inte av denna Orca-build.",
        },
        "settings": {
            "process": process_values,
            "printer": printer_values,
            "build_volume": build_volume,
            "filaments": filament_entries,
            "derived_flow": _flow_estimates(process_values, printer_values, filament_values),
        },
        "model": {
            "object_count": int(model.object_count()),
            "instance_count": instance_count,
            "count_semantics": "Orca objects/instances; not guaranteed physical disconnected part count",
            "physical_part_count": None,
            "project_extent_mm": _xyz(box.size) if box.defined else None,
            "project_extent_scope": "entire_project_all_plates_not_single_plate",
            "mesh_errors": errors,
            "objects": objects,
        },
        "slicing": {
            "observer": "Orca AI Slice Observer",
            "observer_selected_in_active_process": observer_selected,
            "observer_status": observer_status,
            "observer_runtime": observer_runtime,
            "captured_plate_count": len(plate_snapshots),
            "plate_snapshots": plate_snapshots,
            "last_snapshot": slice_snapshot,
            "analysis_scope": {
                "captured_plate_numbers": captured_plate_numbers,
                "complete_for_reported_project": complete_for_reported_project,
                "required_behavior": "Analyze every captured plate for project-wide questions; never default to only the latest snapshot.",
            },
            "freshness_note": "Snapshotet gäller senaste genomförda slicing och kan vara inaktuellt efter projektändringar.",
        },
    }


def _context_for_ai(context):
    """Put a strict all-plate contract first and remove active-plate ambiguities."""
    result = json.loads(json.dumps(context, ensure_ascii=False))
    slicing = result.get("slicing", {})
    snapshots = slicing.pop("plate_snapshots", None) or []
    slicing.pop("last_snapshot", None)
    slicing.pop("primary_snapshot_source", None)
    plate_map = {}
    for index, snapshot in enumerate(snapshots, start=1):
        plate_number = snapshot.get("plate_index_1_based")
        key = f"plate_{plate_number}" if isinstance(plate_number, int) else f"capture_{index}"
        plate_map[key] = snapshot

    # is_printable() in the live multi-plate model is relative to the active GUI
    # plate and must not be presented to the model as a project-wide exclusion.
    for model_object in result.get("model", {}).get("objects", []):
        for instance in model_object.get("instances", []):
            if "printable" in instance:
                instance["active_gui_plate_printable_state"] = instance.pop("printable")
                instance["printable_state_scope"] = "active GUI plate only; not project exclusion"

    scope = slicing.get("analysis_scope", {})
    plate_numbers = scope.get("captured_plate_numbers", [])
    contract = {
        "captured_plate_count": len(plate_map),
        "captured_plate_numbers": plate_numbers,
        "required_sections_for_general_project_questions": [f"Platta {number}" for number in plate_numbers],
        "complete_for_reported_project": scope.get("complete_for_reported_project", False),
        "authoritative_source": "sliced_plates",
        "rules": [
            "Analyze every entry in sliced_plates unless the user explicitly asks about only one plate.",
            "Do not call a captured plate or its objects missing, disabled, or unprintable.",
            "Do not use active_gui_plate_printable_state as a project-wide inclusion flag.",
            "Never equate Orca object/instance count with physical part count when mesh component count is unavailable.",
        ],
        "quantity_semantics": {
            "orca_objects_and_instances_are_physical_part_counts": False,
            "mesh_connected_component_count_available": False,
            "required_wording": "Describe sliced Orca objects/instances; physical loose-part quantity is unknown unless independently verified.",
        },
    }
    return {"analysis_contract": contract, "sliced_plates": plate_map, **result}


def _slice_bbox_mm(print_object):
    values = print_object.bounding_box()
    minimum = [round(orca.slicing.unscale(values[0]), 2),
               round(orca.slicing.unscale(values[1]), 2)]
    maximum = [round(orca.slicing.unscale(values[2]), 2),
               round(orca.slicing.unscale(values[3]), 2)]
    return {
        "min": minimum,
        "max": maximum,
        "size": [round(maximum[0] - minimum[0], 2),
                 round(maximum[1] - minimum[1], 2)],
        "center": [round((minimum[0] + maximum[0]) / 2, 2),
                   round((minimum[1] + maximum[1]) / 2, 2)],
        "coordinate_frame": "object_local_slicing_xy_not_bed_position",
    }


def _slice_snapshot(context):
    sliced_print = context.print
    print_objects = list(sliced_print.objects())
    objects = []
    plate_layer_count = 0
    objects_with_support = 0
    for print_object in print_objects:
        model_object = print_object.model_object()
        layers = list(print_object.layers())
        support_layers = list(print_object.support_layers())
        plate_layer_count = max(plate_layer_count, len(layers))
        if support_layers:
            objects_with_support += 1
        heights = [round(float(layer.height), 3) for layer in layers]
        try:
            snapshot_instances = [_instance_context(instance) for instance in model_object.instances()]
        except Exception:
            snapshot_instances = []
        objects.append({
            "id": int(model_object.id()),
            "name": str(model_object.name or "Namnlöst objekt"),
            "instance_count_in_slice_snapshot": int(model_object.instance_count()),
            "layer_count": len(layers),
            "layer_height_min_mm": min(heights) if heights else None,
            "layer_height_max_mm": max(heights) if heights else None,
            "top_print_z_mm": round(float(layers[-1].print_z), 2) if layers else None,
            "support_or_raft_layer_count": len(support_layers),
            "sliced_xy_bbox_mm": _slice_bbox_mm(print_object),
            "instances_in_slice_snapshot": snapshot_instances,
        })
    try:
        plate_index = int(sliced_print.model().current_plate_index()) + 1
    except Exception:
        plate_index = None
    return {
        "captured_at_epoch": int(time.time()),
        "pipeline_step": "psSkirtBrim",
        "plate_index_1_based": plate_index,
        "object_count": len(print_objects),
        "plate_layer_count": plate_layer_count,
        "objects_with_generated_support_or_raft": objects_with_support,
        "objects": objects,
        "layout_limitations": {
            "sliced_xy_bbox_scope": "object-local; not usable as bed position",
            "instance_world_bbox_scope": "relative project placement; current plate origin/offset is unavailable",
            "final_brim_geometry_available": False,
        },
        "limitations": "Read-only slice snapshot; estimated time and filament usage are not exposed at this pipeline step.",
    }


class OrcaAiSliceObserver(orca.slicing.SlicingPipelineCapabilityBase):
    def get_name(self):
        return "Orca AI Slice Observer"

    def execute(self, context):
        try:
            step_name = str(context.step)
        except Exception:
            step_name = "unknown"
        with SLICE_DATA_LOCK:
            OBSERVER_RUNTIME["execute_calls"] += 1
            OBSERVER_RUNTIME["last_execute_at_epoch"] = int(time.time())
            OBSERVER_RUNTIME["last_step"] = step_name
        if context.step != orca.slicing.Step.psSkirtBrim or context.print is None:
            return orca.ExecutionResult.success()
        if context.cancelled():
            return orca.ExecutionResult.skipped()
        global LAST_SLICE_SNAPSHOT
        try:
            snapshot = _slice_snapshot(context)
        except Exception as error:
            snapshot = {
                "captured_at_epoch": int(time.time()),
                "pipeline_step": "psSkirtBrim",
                "error": str(error),
            }
        with SLICE_DATA_LOCK:
            LAST_SLICE_SNAPSHOT = snapshot
            plate_index = snapshot.get("plate_index_1_based")
            if isinstance(plate_index, int) and plate_index > 0:
                SLICE_SNAPSHOTS_BY_PLATE[plate_index] = snapshot
        # Analysis must never block or alter the user's slicing job.
        return orca.ExecutionResult.success()


def _output_text(response):
    parts = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    parts.append(content["text"])
    return "\n".join(parts).strip()


def _http_error(error):
    try:
        data = json.loads(error.read().decode("utf-8", errors="replace"))
        return str(data.get("error", {}).get("message") or f"HTTP {error.code}")
    except Exception:
        return f"OpenAI API svarade med HTTP {error.code}."


def _api_key_error(key):
    if not key:
        return "Ingen API-nyckel är konfigurerad."
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return ("API-nyckeln innehåller ett typografiskt eller annat icke-ASCII-tecken, "
                "till exempel – i stället för vanligt -. Kopiera nyckeln på nytt direkt "
                "från OpenAI och klistra in den utan extra text.")
    if any(character.isspace() for character in key):
        return ("API-nyckeln innehåller mellanslag eller radbrytning. Kopiera nyckeln "
                "på nytt direkt från OpenAI.")
    if not key.startswith("sk-"):
        return "API-nyckeln ser inte ut som en OpenAI-nyckel; den ska börja med sk-."
    return None


class OrcaAiPage(orca.pages.PagesPluginCapabilityBase):
    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.key_source = "miljövariabel" if self.api_key else "ingen"
        self.model = os.environ.get("ORCA_AI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.previous_id = None
        self.busy = False
        self.lock = threading.Lock()

    def get_name(self):
        return "Orca AI"

    def get_ui(self):
        return PAGE_HTML

    def send_session(self):
        self.post_message({
            "type": "session", "key_configured": bool(self.api_key),
            "key_source": self.key_source, "model": self.model,
            "key_problem": _api_key_error(self.api_key) if self.api_key else None,
        })

    def start_chat(self, question, plate_count=None, experience_level="experienced",
                   response_mode="quick"):
        question = question.strip()
        if not question:
            self.post_message({"type": "error", "message": "Skriv en fråga först."})
            return
        if not self.api_key:
            self.post_message({"type": "error", "message": "Lägg in en OpenAI API-nyckel och välj Använd denna session."})
            return
        key_problem = _api_key_error(self.api_key)
        if key_problem:
            self.post_message({"type": "error", "message": key_problem})
            return
        with self.lock:
            if self.busy:
                self.post_message({"type": "error", "message": "En fråga behandlas redan."})
                return
            self.busy = True
        try:
            context = collect_context(plate_count)
        except Exception as error:
            with self.lock:
                self.busy = False
            self.post_message({"type": "error", "message": f"Kunde inte läsa projektet: {error}"})
            return
        experience_level = experience_level if experience_level in EXPERIENCE_INSTRUCTIONS else "experienced"
        response_mode = response_mode if response_mode in RESPONSE_MODE_INSTRUCTIONS else "quick"
        threading.Thread(target=self.chat_worker,
                         args=(question, context, experience_level, response_mode),
                         name="OrcaAiRequest", daemon=True).start()

    def chat_worker(self, question, context, experience_level, response_mode):
        try:
            ai_context = _context_for_ai(context)
            contract = ai_context.get("analysis_contract", {})
            captured = contract.get("captured_plate_numbers", [])
            scope_instruction = (
                "OBLIGATORISKT SVARSKONTRAKT:\n"
                f"- {len(captured)} skivade plattor är fångade: {captured}.\n"
                "- Om frågan gäller hela projektet ska varje fångad platta omfattas. "
                "I snabbkontroll räcker en kompakt rad per platta; i djup analys kan rubriker användas.\n"
                "- Läs varje post i sliced_plates. Säg inte att en fångad platta saknas.\n"
                "- Globala printable-värden beskriver aktiv GUI-platta och får inte tolkas som projektomfattande exkludering.\n"
                if captured else ""
            )
            text = (scope_instruction + "AKTUELL PROJEKTKONTEXT (JSON):\n"
                    + json.dumps(ai_context, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nANVÄNDARENS FRÅGA:\n" + question)
            payload = {
                "model": self.model,
                "instructions": (SYSTEM_PROMPT + "\n\n"
                                 + EXPERIENCE_INSTRUCTIONS[experience_level] + "\n\n"
                                 + RESPONSE_MODE_INSTRUCTIONS[response_mode]),
                "input": text,
                "max_output_tokens": 1600 if response_mode == "quick" else 4000,
            }
            if self.previous_id:
                payload["previous_response_id"] = self.previous_id
            request = Request(
                OPENAI_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = _output_text(result)
            if not answer:
                raise RuntimeError("API-svaret innehöll ingen text.")
            if result.get("status") == "incomplete":
                reason = result.get("incomplete_details", {}).get("reason", "okänd orsak")
                answer += ("\n\n> ⚠️ Svaret avbröts av API:t (" + str(reason)
                           + "). Skriv **fortsätt** för resten.")
            self.previous_id = result.get("id")
            self.post_message({"type": "answer", "text": answer})
        except HTTPError as error:
            self.post_message({"type": "error", "message": _http_error(error)})
        except URLError as error:
            self.post_message({"type": "error", "message": f"Nätverksfel: {error.reason}"})
        except Exception as error:
            self.post_message({"type": "error", "message": f"AI-anropet misslyckades: {error}"})
        finally:
            with self.lock:
                self.busy = False

    def on_message(self, message):
        try:
            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "context":
                self.post_message({
                    "type": "context",
                    "payload": collect_context(message.get("plate_count")),
                })
            elif kind == "session_status":
                self.send_session()
            elif kind == "session":
                key = str(message.get("api_key", "")).strip()
                model = str(message.get("model", "")).strip()
                if key:
                    key_problem = _api_key_error(key)
                    if key_problem:
                        self.post_message({"type": "error", "message": key_problem})
                        return
                    self.api_key, self.key_source = key, "denna session"
                if model:
                    self.model = model
                self.previous_id = None
                self.send_session()
            elif kind == "chat":
                self.start_chat(
                    str(message.get("text", "")), message.get("plate_count"),
                    str(message.get("experience_level", "experienced")),
                    str(message.get("response_mode", "quick")),
                )
            elif kind == "tuning_calculate":
                try:
                    result = tuning_calculation(
                        str(message.get("calculation", "")), message.get("values", {})
                    )
                    self.post_message({"type": "tuning_result", "payload": result})
                except ValueError as error:
                    self.post_message({"type": "tuning_error", "message": str(error)})
            elif kind == "clear":
                self.previous_id = None
                self.post_message({"type": "cleared"})
        except Exception as error:
            self.post_message({"type": "error", "message": f"Pluginfel: {error}"})


@orca.plugin
class OrcaAiPlugin(orca.base):
    def register_capabilities(self):
        orca.register_capability(OrcaAiPage)
        orca.register_capability(OrcaAiSliceObserver)
