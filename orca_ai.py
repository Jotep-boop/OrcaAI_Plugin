# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.orcaslicer.plugin]
# name = "Orca AI"
# description = "Context-aware OrcaSlicer help through the OpenAI Responses API."
# author = "Jeppe"
# version = "0.5.6"
# ///

"""Orca AI 0.5.6 for OrcaSlicer 2.5.0-dev build ac3997c0."""

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
SYSTEM_PROMPT = """Du är Orca AI, en försiktig expert på FFF/FDM och OrcaSlicer.
Svara på svenska, konkret och lättläst. Utgå från projektkontexten och skilj
alltid på fakta, bedömning och saknad information. Låtsas aldrig att du har
ändrat något: du är rådgivande och kan ännu inte skriva till OrcaSlicer.

VIKTIGT OM BYGGPLATTOR:
- model.project_extent_mm omfattar hela projektet och kan sträcka sig över flera
  byggplattor. Jämför ALDRIG detta mått med storleken på en enda byggplatta.
- Orcas plugin-API i denna version anger inte vilken platta varje objekt tillhör.
- Om plates.reported_count är större än 1 ska du tydligt säga att passformen per
  platta inte kan verifieras automatiskt. Gissa inte plattillhörighet från XY-läge.
- Använd endast settings.build_volume för bäddens verkliga mått. Gissa aldrig
  byggytan från skrivarens namn.
- Skilj på model.object_count och model.instance_count. Filnamn som innehåller
  x2/x4 är bara en möjlig ledtråd, aldrig bevis på önskat antal.
- object_count, instance_count och instance_count_in_slice_snapshot räknar
  Orca-objekt/instanser, INTE säkert fysiska lösa delar. En enda STL och en enda
  Orca-instans kan innehålla flera frånkopplade meshkroppar, till exempel fyra
  clamps i en fil med suffixet _x4. Skriv därför "ett skivat Orca-objekt från
  Belt_Clamp_x4.stl", aldrig "en Belt Clamp", om antal meshkomponenter saknas.
  Ange physical_part_count som okänt och be användaren kontrollera preview/BOM.

FORMAT:
- Svara normalt med högst cirka 700 ord; prioritera avvikelser och konkreta råd.
- Använd Markdown-rubriker, korta stycken och punktlistor. Använd ALDRIG
  Markdown-tabeller eller HTML; chattytan är för smal för tabeller.
- Lista inte varje inställning som redan är bra. Samla godkända kontroller kort.
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
- Ställ en kort följdfråga när underlaget inte räcker."""

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
    button{border:0;border-radius:8px;padding:9px 13px;cursor:pointer;font-weight:600;background:var(--orca-accent);color:var(--orca-accent-fg)}
    button.secondary{background:transparent;color:var(--orca-fg);border:1px solid var(--orca-border)}
    button:disabled{opacity:.5;cursor:default}
    textarea,input{border:1px solid var(--orca-border);border-radius:8px;padding:10px 11px;background:var(--orca-bg);color:var(--orca-fg);font-family:inherit}
    textarea{flex:1;min-width:0;min-height:48px;max-height:130px;resize:vertical}.composer{align-items:flex-end}.composer button{min-height:48px}
    input{width:100%}.field{margin-top:10px}.field label{display:block;font-size:11px;color:var(--orca-muted);margin-bottom:5px}
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
      <div class="panel-head"><h2>Chatt</h2><button class="secondary" id="clear">Rensa</button></div>
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
const $=id=>document.getElementById(id);let busy=false;
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
function add(role,text){const s=$("starter");if(s)s.remove();const e=document.createElement("div");e.className="message "+role;if(role==="assistant")e.innerHTML=renderMarkdown(text);else e.textContent=text;$("chat").appendChild(e);$("chat").scrollTop=$("chat").scrollHeight}
function getContext(){status("Läser projekt","busy");window.orca.postMessage({type:"context",plate_count:plateCount()})}
function send(text){const q=String(text||"").trim();if(!q||busy)return;add("user",q);$("prompt").value="";setBusy(true);window.orca.postMessage({type:"chat",text:q,plate_count:plateCount()})}
window.orca.onMessage(m=>{
  if(!m||!m.type)return;
  if(m.type==="context"){const c=m.payload;$("printer").textContent=c.printer;$("process").textContent=c.process;$("filaments").textContent=c.filaments.join(", ")||"Inga";const z=c.model.project_extent_mm;$("model").textContent=c.model.object_count+" objekt · "+c.model.instance_count+" instanser"+(z?" · "+z.map(v=>Number(v).toFixed(1)).join(" × ")+" mm totalt":"");const s=c.slicing||{},snap=s.last_snapshot,n=Number(s.captured_plate_count||0);if(snap&&snap.error)$("slice-info").textContent="Kördes, men analysen misslyckades: "+snap.error;else if(snap)$("slice-info").textContent=(n>1?n+" plattor fångade":"Snapshot fångad")+" · senast "+(snap.plate_index_1_based?"platta "+snap.plate_index_1_based+" · ":"")+snap.object_count+" objekt · "+snap.plate_layer_count+" lager";else if(s.observer_status==="not_selected")$("slice-info").textContent="Inte vald i den aktiva processprofilen";else if(s.observer_status==="selected_waiting")$("slice-info").textContent="Vald · väntar på ny slicing efter pluginstart";else if(s.observer_status==="ran_without_snapshot")$("slice-info").textContent="Kördes, men inget snapshot skapades · se diagnostik";else $("slice-info").textContent="Kan inte läsa valet i den aktiva processprofilen";$("context").textContent=JSON.stringify(c,null,2);if(!busy)status("Redo","ready")}
  if(m.type==="session"){ $("model-name").value=m.model;const bad=Boolean(m.key_problem);$("key-status").textContent=bad?"API-nyckeln innehåller ogiltiga tecken":(m.key_configured?"API-nyckel aktiv ("+m.key_source+")":"Ingen nyckel konfigurerad");$("key-dot").className="dot "+(bad?"error":(m.key_configured?"ready":""));$("key").value=""}
  if(m.type==="answer"){setBusy(false);add("assistant",m.text)}
  if(m.type==="error"){setBusy(false);add("error",m.message)}
  if(m.type==="cleared"){$("chat").innerHTML='<div class="starter" id="starter"><h2>Ny konversation</h2><div class="muted">Projektkontexten läses om vid varje fråga.</div></div>'}
});
$("send").onclick=()=>send($("prompt").value);
$("prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send(e.target.value)}};
document.querySelectorAll(".quick button").forEach(b=>b.onclick=()=>send(b.textContent));
$("refresh").onclick=getContext;$("plate-count").onchange=getContext;$("clear").onclick=()=>window.orca.postMessage({type:"clear"});
$("save").onclick=()=>window.orca.postMessage({type:"session",api_key:$("key").value,model:$("model-name").value});
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
    "filament_flow_ratio", "nozzle_temperature",
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

    def start_chat(self, question, plate_count=None):
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
        threading.Thread(target=self.chat_worker, args=(question, context),
                         name="OrcaAiRequest", daemon=True).start()

    def chat_worker(self, question, context):
        try:
            ai_context = _context_for_ai(context)
            contract = ai_context.get("analysis_contract", {})
            captured = contract.get("captured_plate_numbers", [])
            scope_instruction = (
                "OBLIGATORISKT SVARSKONTRAKT:\n"
                f"- {len(captured)} skivade plattor är fångade: {captured}.\n"
                f"- Om användaren inte uttryckligen begränsar frågan till en platta måste svaret innehålla dessa rubriker: "
                + ", ".join(f"Platta {number}" for number in captured) + ".\n"
                "- Läs varje post i sliced_plates. Säg inte att en fångad platta saknas.\n"
                "- Globala printable-värden beskriver aktiv GUI-platta och får inte tolkas som projektomfattande exkludering.\n"
                "- Kontrollera att alla obligatoriska plattrubriker finns innan svaret avslutas.\n\n"
                if captured else ""
            )
            text = (scope_instruction + "AKTUELL PROJEKTKONTEXT (JSON):\n"
                    + json.dumps(ai_context, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nANVÄNDARENS FRÅGA:\n" + question)
            payload = {
                "model": self.model,
                "instructions": SYSTEM_PROMPT,
                "input": text,
                "max_output_tokens": 4000,
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
                self.start_chat(str(message.get("text", "")), message.get("plate_count"))
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
