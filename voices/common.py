"""Shared pieces for rendering Walk Chicago narration to audio files.

Each engine script supplies one function, synth(text) -> (pcm_bytes, sample_rate),
that returns 16-bit mono PCM for a single sentence. This module splits tracks into
sentences, stitches the sentence audio together with short pauses, encodes the result,
and records when each sentence starts so the app can highlight and seek by sentence.
"""
import json, os, re, subprocess, sys, tempfile, wave
from pathlib import Path

HERE = Path(__file__).parent
SENTENCE_GAP = 0.28    # seconds of silence after each sentence
PARAGRAPH_GAP = 0.70   # seconds of silence after each paragraph
LEAD_IN = 0.30

# Same pronunciation fixes the app applies to on-device speech.
SPEAK_FIX = [
    (r"\bSt\. (?=[A-Z])", "Saint "), (r"\bAT&T\b", "A T and T"), (r"&", " and "),
    # Chicago names the voices get wrong (respelled for the ear). Keep in step with SPEAK_FIX in index.html.
    (r"\bMies\b", "Meese"), (r"\bvan der Rohe\b", "van der Roh-uh"), (r"\bJolliet\b", "Jo-lee-et"),
    (r"\bMonadnock\b", "Muh-nad-nock"), (r"\bMiró", "Mee-roh"), (r"\bPotawatomi\b", "Pot-uh-wot-uh-mee"),
    (r"\bCermak\b", "Sir-mack"), (r"\bPaderewski\b", "Pad-eh-ref-skee"), (r"\bGehry\b", "Gary"),
    (r"\bSeurat\b", "Sur-rah"), (r"\bGrande Jatte\b", "Grahnd Zhaht"), (r"\bBueller\b", "Byoo-ler"),
    (r"\bVolodymyr\b", "Vo-lo-dih-meer"), (r"\bRusyn(?=s?\b)", "Roo-sin"), (r"\bJiménez\b", "Hee-meh-nez"),
    (r"\bAlbizu\b", "Al-bee-soo"), (r"\bjibarito", "hee-bah-ree-toe"), (r"\bStefanovic\b", "Steh-fah-no-vich"),
    (r"\bGiancana\b", "Jan-kah-na"), (r"\bNetsch\b", "Netch"), (r"\bJuárez\b", "Hwah-rez"),
    (r"Plzeň", "Pull-zen"), (r"\bMasaryk\b", "Mah-sah-rick"), (r"\bMinnekirken\b", "Minneh-keer-ken"),
    (r"\bJackowo\b", "Yats-koh-vo"), (r"\bDuSable\b", "Doo-Sah-bul"), (r"\bLoeb\b", "Lobe"),
    (r"\bMamah\b", "May-mah"), (r"\bTaliesin\b", "Tally-essin"), (r"\bGoethe Street\b", "Go-thee Street"),
    (r"\bDes Plaines\b", "Dess Plains"), (r"\bPaulina\b", "Paw-lie-na"), (r"\bBoricua\b", "Bo-ree-kwa"),
    (r"\bBorikén", "Bo-ree-ken"), (r"\bpysanky\b", "pih-sahn-kih"), (r"\bpysanka\b", "pih-sahn-kah"),
    (r"\bKnute\b", "Noot"), (r"\bRockne\b", "Rock-nee"), (r"\bSkandinaven\b", "Skahn-dee-nah-ven"),
    (r"\bMi Tocaya\b", "Mee Toh-kai-yah"), (r"\bantojos\b", "ahn-toh-hohs"), (r"\bDávila\b", "Dah-vee-lah"),
    (r"\bSpies\b", "Speez"), (r"\bNeebe\b", "Nee-bee"), (r"\bMacSwiney\b", "Mac-Swee-nee"), (r"\bPeloponnese\b", "Pel-o-po-neez"),
    (r"\bApostolou\b", "Ah-po-stoh-loo"), (r"\bBrach\b", "Brock"), (r"\bSchnering\b", "Shner-ing"), (r"\bWeinert\b", "Wine-ert"), (r"\bGelert\b", "Geh-lert"),
    (r"\bDamen\b", "Dam-en"), (r"\bBochco\b", "Botch-ko"), (r"\bEsterhaus\b", "Ester-house"), (r"\bCanzoneri\b", "Kan-zo-nair-ee"), (r"\bBuscher\b", "Boo-sher"),
    (r"\bToussaint\b", "Too-sahn"), (r"\bMenard\b", "Meh-nard"), (r"\bPasquale\b", "Pahs-kwah-lee"), (r"\bgiardiniera\b", "jar-dih-nair-ah"), (r"\bGautreaux\b", "Go-troh"),
    (r"\bAndrzej\b", "Ahn-jay"), (r"\bDajnowski\b", "Dye-noff-skee"), (r"\bStroger\b", "Stroh-gur"), (r"\bReichel\b", "Rye-kel"), (r"\bKraig\b", "Craig"), (r"\bchampurrado\b", "cham-poo-rah-doh"),
    (r"\bZdrůbek\b", "Zdroo-bek"), (r"\bGeringer\b", "Geh-ring-er"), (r"\bGarrigue\b", "Gah-reeg"), (r"\bTomáš", "Toh-mahsh"), (r"\bNárod\b", "Nah-rod"), (r"\bVojtěch\b", "Voy-tyekh"), (r"\bBolesław\b", "Bo-leh-swahf"),
    (r"\bGniezno\b", "Gnyez-no"), (r"\bHouby\b", "Hoe-bee"), (r"\bPietà", "Pee-ay-tah"), (r"\bRamírez\b", "Rah-mee-res"), (r"\bVázquez\b", "Vahs-kes"), (r"\bFroebel\b", "Fro-bel"), (r"\bChuy\b", "Choo-ee"),
    (r"\bJesús\b", "Heh-soos"), (r"\bMaiotis\b", "My-oh-tis"), (r"\bOaxaca\b", "Wah-hah-kah"), (r"\bCiudad\b", "See-oo-dahd"), (r"\bPuebla\b", "Pweb-lah"), (r"\bVasconcelos\b", "Vahs-kon-seh-lohs"), (r"\bOrozco\b", "Oh-rohs-koh"),
    (r"\bSiqueiros\b", "See-kay-rohs"), (r"\bPatlán\b", "Paht-lahn"), (r"\bRaya\b", "Rah-yah"), (r"\bAztlán\b", "Ahst-lahn"), (r"\bTepeyac\b", "Teh-peh-yahk"), (r"\bNahuatl\b", "Nah-wah-tul"), (r"\bcempasúchil\b", "sem-pah-soo-cheel"),
    (r"\bmuerto\b", "mwair-toh"), (r"\borejas\b", "oh-reh-hahs"), (r"\bcuernos\b", "kwair-nohs"), (r"\bmarranitos\b", "mah-rah-nee-tohs"), (r"\bpiloncillo\b", "pee-lon-see-yo"), (r"\breyes\b", "ray-ess"), (r"\bCarbajal\b", "Kar-bah-hahl"),
    (r"\bInocencio\b", "Ee-no-sen-syo"), (r"\bUruapan\b", "Oo-roo-ah-pahn"), (r"\bMichoacán\b", "Mee-cho-ah-kahn"), (r"\bpaletería\b", "pah-leh-teh-ree-ah"), (r"\bpaletas\b", "pah-leh-tahs"), (r"\bMuskegon\b", "Muss-kee-gun"), (r"\bMenominee\b", "Meh-nom-ih-nee"),
    (r"\bSchenectady\b", "Skuh-nek-tuh-dee"),
    (r"\bZhongshan\b", "Jong-shahn"), (r"\bMacau\b", "Muh-cow"), (r"\bQing\b", "Ching"), (r"\bWuchang\b", "Woo-chahng"), (r"\bShikai\b", "Shir-kye"), (r"\bYuan\b", "Yoo-ahn"), (r"\bNian\b", "Nyen"),
    (r"\bguo\b", "gwoh"), (r"\bfu\b", "foo"), (r"\bpaifang\b", "pie-fahng"), (r"\bTaishan\b", "Tie-shahn"), (r"\bToisan\b", "Toy-sahn"), (r"\bGuangzhou\b", "Gwahng-joe"), (r"\bKaiping\b", "Kye-ping"),
    (r"\bdiaolou\b", "dyow-loh"), (r"\bSiu\b", "Sue"), (r"\bsiu\b", "syoo"), (r"\bbao\b", "bow"), (r"\bBeihai\b", "Bay-hye"), (r"\bQianlong\b", "Chyen-loong"), (r"\bQu\b", "Choo"),
    (r"\bYangtze\b", "Yang-see"), (r"\bMiluo\b", "Mee-lwoh"), (r"\bzongzi\b", "dzong-dzuh"), (r"\bTian\b", "Tyen"), (r"\bXia\b", "Shyah"),
    (r"\bVeeck\b", "Veck"), (r"\bSioux\b", "Soo"), (r"\bBougainville\b", "Boo-gun-vil"), (r"\bGaedel\b", "Gay-dell"), (r"\bDraugas\b", "Drow-gus"), (r"\bLituanica\b", "Lit-oo-ah-nik-uh"), (r"\bKaunas\b", "Kow-nus"), (r"\bSteponas\b", "Steh-poh-nus"), (r"\bStasys\b", "Stah-sees"), (r"\bGirėnas\b", "Gih-ray-nus"), (r"\bChanute\b", "Shuh-noot"), (r"\bSheil\b", "Sheel"),
]

def to_speech(t):
    for pat, rep in SPEAK_FIX:
        t = re.sub(pat, rep, t)
    return t

_ABBR = re.compile(r"^(St|Mr|Mrs|Dr|Mt|Ft|vs|Co|No)\.$")
def split_sentences(par):
    """Port of the app's sentence splitter: never splits after initials or 'St.'."""
    out, start = [], 0
    for m in re.finditer(r"[.!?][\"”’']?(?=\s+[\"“‘']?[A-Z0-9])", par):
        end = m.end()
        seg = par[start:end]
        last = seg.split()[-1] if seg.split() else ""
        if _ABBR.match(last) or re.fullmatch(r"[A-Z]\.", last) or re.fullmatch(r"(?:[A-Z]\.){2,}", last):
            continue
        out.append(seg.strip()); start = end
    rest = par[start:].strip()
    if rest: out.append(rest)
    return out

def paragraphs(text):
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

def silence(sec, rate):
    return b"\x00\x00" * int(sec * rate)

def render_text(text, synth):
    """Returns (pcm, rate, sentences) where sentences = [[paragraph, start_sec, display_text], ...]."""
    pcm, rate, sents = bytearray(), None, []
    paras = paragraphs(text)
    for pi, p in enumerate(paras):
        ss = split_sentences(p)
        for si, s in enumerate(ss):
            audio, r = synth(to_speech(s))
            if rate is None:
                rate = r; pcm += silence(LEAD_IN, rate)
            sents.append([pi, round(len(pcm) / 2 / rate, 3), s])
            pcm += audio
            pcm += silence(PARAGRAPH_GAP if si == len(ss) - 1 and pi < len(paras) - 1 else SENTENCE_GAP, rate)
    return bytes(pcm), rate, sents

def write_wav(path, pcm, rate):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)

def encode(wav_path, out_path):
    """mp3 via ffmpeg where available, else AAC (.m4a) via macOS afconvert."""
    if out_path.suffix == ".mp3":
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-ac", "1", "-b:a", "64k", str(out_path)], check=True)
    else:
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", str(wav_path), str(out_path)], check=True)

def pick_ext():
    from shutil import which
    if which("ffmpeg"): return ".mp3"
    if which("afconvert"): return ".m4a"
    sys.exit("Need ffmpeg (Linux: sudo apt install ffmpeg) or macOS afconvert to encode audio.")

def render_one(text, synth, out_path):
    pcm, rate, sents = render_text(text, synth)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "t.wav"; write_wav(wav, pcm, rate); encode(wav, out_path)
    return round(len(pcm) / 2 / rate, 2), sents

def run_sample(engine, voices, synth_for_voice):
    ext = pick_ext(); out = HERE / "samples"; out.mkdir(exist_ok=True)
    text = (HERE / "sample.txt").read_text()
    for v in voices:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", v).strip("_")
        path = out / f"{engine}-{safe}{ext}"
        print(f"  {v} -> {path.name}", flush=True)
        try:
            render_one(text, synth_for_voice(v), path)
        except Exception as e:
            print(f"    failed: {e}")
    print(f"\nDone. Listen to the files in {out}")

def run_all(engine, voice_label, synth, limit=None):
    ext = pick_ext()
    out = HERE / "out" / "audio"; out.mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"tracks": {}}
    if manifest.get("voice") not in (None, f"{engine}:{voice_label}"):
        sys.exit(f"out/audio already holds a different voice ({manifest['voice']}). Move it aside first.")
    manifest["voice"] = f"{engine}:{voice_label}"
    tracks = json.loads((HERE / "tracks.json").read_text())[:limit]
    for n, t in enumerate(tracks, 1):
        fname = t["file"] + ext
        if t["key"] in manifest["tracks"] and (out / fname).exists():
            continue
        print(f"[{n}/{len(tracks)}] {t['title']}", flush=True)
        dur, sents = render_one(t["text"], synth, out / fname)
        manifest["tracks"][t["key"]] = {"file": "audio/" + fname, "dur": dur, "s": sents}
        mpath.write_text(json.dumps(manifest, ensure_ascii=False))  # save as we go, so a rerun resumes
    total = sum(v["dur"] for v in manifest["tracks"].values())
    print(f"\nDone: {len(manifest['tracks'])} tracks, {total/3600:.1f} hours of audio in {out}")
    print("Next: bash upload_r2.sh  (or bash publish_audio.sh; see SHIPPING.md)")
