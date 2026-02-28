import json, logging, shutil, subprocess, threading
from pathlib import Path
from typing import Optional, Dict, Any, Union
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class AudioProcessorError(Exception):
    """Base exception for audio processing."""


class CommandExecutionError(AudioProcessorError):
    """Command execution failed."""


class CommandTimeoutError(AudioProcessorError):
    """Command timed out."""


def run_command(
    command: list[str], timeout: int = 300, description: str = "", check: bool = True
) -> subprocess.CompletedProcess:
    """Execute subprocess command with timeout and error handling."""
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty list")
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError(f"timeout must be positive integer, got {timeout}")

    cmd_str = " ".join(str(arg) for arg in command)
    if description:
        logger.debug(f"Executing: {description}")
    logger.debug(f"Command: {cmd_str}")

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
        if result.stdout:
            logger.debug(f"Command stdout: {result.stdout[:500]}")
        if result.stderr:
            logger.debug(f"Command stderr: {result.stderr[:500]}")

        if check and result.returncode != 0:
            error_msg = (
                result.stderr.strip()
                if result.stderr
                else f"Exit code {result.returncode}"
            )
            logger.error(f"Command failed: {cmd_str}\nError: {error_msg}")
            raise CommandExecutionError(f"Command failed: {error_msg}")
        return result
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {timeout}s: {cmd_str}")
        raise CommandTimeoutError(f"Command timed out after {timeout}s") from e
    except Exception as e:
        if isinstance(e, AudioProcessorError):
            raise
        raise CommandExecutionError(str(e))


def build_ffmpeg_command(
    input_file: str,
    output_file: str,
    filters: list = None,
    codec_args: dict = None,
    extra_args: list = None,
) -> list[str]:
    """Build FFmpeg command with proper argument ordering."""
    cmd = ["ffmpeg", "-i", input_file]
    if filters:
        cmd.extend(["-af", ",".join(filters)])
    for k, v in (codec_args or {}).items():
        cmd.extend([f"-{k}", str(v)])
    if extra_args:
        cmd.extend(extra_args)
    return cmd + ["-y", output_file]


def build_sox_command(
    input_file: str,
    output_file: str,
    effects: list = None,
    rate: int = None,
    channels: int = None,
) -> list[str]:
    """Build SoX command with proper argument ordering."""
    cmd = ["sox", input_file, output_file]
    if rate:
        cmd.extend(["rate", str(rate)])
    if channels:
        cmd.append("remix -" if channels == 1 else "remix 1,2")
    return cmd + (effects or [])


def check_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def check_sox_available() -> bool:
    return shutil.which("sox") is not None


def _get_ver(bin_n: str, arg: str = "-version") -> Optional[str]:
    """Get version string of a binary."""
    try:
        res = subprocess.run([bin_n, arg], capture_output=True, text=True, timeout=5)
        return res.stdout.split("\n")[0].strip() if res.returncode == 0 else None
    except:
        return None


def get_ffmpeg_version() -> Optional[str]:
    return _get_ver("ffmpeg")


def get_sox_version() -> Optional[str]:
    return _get_ver("sox", "-V")


class AudioProcessor:
    """Audio preprocessing pipeline using FFmpeg and SoX."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_params = {
            "silence_threshold_db": -50.0,
            "silence_duration": 0.5,
            "target_sample_rate": 16000,
            "mp3_bitrate": "128k",
            "fade_duration": 0.1,
        }
        self._lock = threading.RLock()
        self._validate_cli_tools_availability()

    def _validate_cli_tools_availability(self):
        """Validate required CLI tools are available."""
        if not check_ffmpeg_available():
            raise RuntimeError("FFmpeg not found")
        logger.info(f"FFmpeg: {get_ffmpeg_version()}")
        if check_sox_available():
            logger.info(f"SoX: {get_sox_version()}")

    def _generate_output_path(
        self, inp: Path, suffix: str = "", ext: str = None, fmt: str = None
    ) -> Path:
        """Generate output path based on input and params."""
        if ext is None:
            ext = ".mp4" if fmt == "mp4" else inp.suffix
        return inp.parent / f"{inp.stem}{suffix}{ext}"

    def get_audio_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Get audio metadata via ffprobe."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(p)
        res = run_command(
            [
                "ffprobe",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(p),
            ],
            timeout=30,
        )
        d = json.loads(res.stdout)
        a = next(
            (s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None
        )
        if not a:
            raise CommandExecutionError(f"No audio stream in {p}")
        f = d.get("format", {})
        return {
            "duration": float(f.get("duration", 0)),
            "sample_rate": int(a.get("sample_rate", 0)),
            "channels": int(a.get("channels", 0)),
            "codec": a.get("codec_name", "unknown"),
            "bitrate": int(f.get("bit_rate", 0)),
            "size_bytes": int(f.get("size", 0)),
            "format": f.get("format_name", "unknown"),
        }

    def trim_silence(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        threshold_db: float = None,
        min_silence_duration: float = None,
    ) -> Path:
        """Remove silence from beginning and end of audio."""
        with self._lock:
            db, dur = (
                threshold_db
                if threshold_db is not None
                else self.default_params["silence_threshold_db"],
                min_silence_duration
                if min_silence_duration is not None
                else self.default_params["silence_duration"],
            )
            if not isinstance(db, (int, float)):
                raise ValueError(f"threshold_db must be numeric, got {type(db)}")
            if not isinstance(dur, (int, float)):
                raise ValueError(
                    f"min_silence_duration must be numeric, got {type(dur)}"
                )
            in_p = Path(input_path)
            if not in_p.exists():
                raise FileNotFoundError(f"Input file not found: {in_p}")
            out_p = (
                Path(output_path)
                if output_path
                else self._generate_output_path(in_p, "_trimmed")
            )
            data, rate = sf.read(in_p)
            mono = data[:, 0] if data.ndim > 1 else data
            win, lin_t = max(1, int(dur * rate)), 10 ** (db / 20.0)
            start = 0
            for i in range(0, len(mono) - win, win // 4):
                if np.sqrt(np.mean(mono[i : i + win] ** 2)) > lin_t:
                    start = i
                    break
            end = len(mono)
            for i in range(len(mono) - win, 0, -win // 4):
                if (
                    i + win <= len(mono)
                    and np.sqrt(np.mean(mono[i : i + win] ** 2)) > lin_t
                ):
                    end = i + win
                    break
            sf.write(out_p, data[start:end] if start < end else data, rate)
            return out_p

    def downsample(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        target_rate: int = None,
        filter_type: str = "high_quality",
        channels: int = 1,
    ) -> Path:
        """Downsample audio to target rate and channels."""
        with self._lock:
            rate = target_rate or self.default_params["target_sample_rate"]
            if not isinstance(rate, int) or rate <= 0:
                raise ValueError(f"Invalid target sample rate: {rate}")
            in_p = Path(input_path)
            if not in_p.exists():
                raise FileNotFoundError(f"Input file not found: {in_p}")
            out_p = (
                Path(output_path)
                if output_path
                else self._generate_output_path(in_p, f"_{rate}Hz", ext=".m4a")
            )
            info = self.get_audio_info(in_p)
            if info["sample_rate"] == rate and info["channels"] == channels:
                if in_p != out_p:
                    shutil.copy2(in_p, out_p)
                return out_p
            f_cfg = {"fast": "0", "medium": "1", "high_quality": "1:cutoff=0.98"}
            flt = [
                f"aresample=resampler=swr:linear_interp={f_cfg.get(filter_type, f_cfg['high_quality'])}"
            ]
            cmd = build_ffmpeg_command(
                str(in_p),
                str(out_p),
                filters=flt,
                codec_args={"acodec": "aac", "ar": rate, "ac": channels, "f": "mp4"},
            )
            run_command(cmd, description="Audio resampling")
            return out_p

    def encode_mp3(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        bitrate: str = None,
        quality: str = "standard",
    ) -> Path:
        """Encode audio to MP3 format."""
        with self._lock:
            br = bitrate or self.default_params["mp3_bitrate"]
            if not isinstance(br, str):
                raise ValueError(f"bitrate must be a string, got {type(br)}")
            in_p = Path(input_path)
            if not in_p.exists():
                raise FileNotFoundError(f"Input file not found: {in_p}")
            out_p = (
                Path(output_path)
                if output_path
                else self._generate_output_path(in_p, ext=".mp3")
            )
            args = {
                "acodec": "mp3",
                "b:a": br,
                "map_metadata": "-1",
                "write_id3v2": "0",
                "fflags": "+bitexact",
            }
            args.update(self._get_quality_params(quality))
            cmd = build_ffmpeg_command(
                str(in_p),
                str(out_p),
                filters=["aresample=16000", "pan=mono|c0=c0"],
                codec_args=args,
            )
            run_command(cmd, description="MP3 encoding")
            return out_p

    def _get_quality_params(self, quality: str) -> Dict[str, Any]:
        """Get FFmpeg quality parameters based on preset."""
        presets = {
            "fast": {"q:a": "5", "compression_level": "1"},
            "standard": {"q:a": "2", "compression_level": "6"},
            "high": {"q:a": "0", "compression_level": "9"},
        }
        return presets.get(quality, presets["standard"])

    def process_pipeline(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        operations: list = None,
    ) -> Path:
        """Execute multiple processing operations in sequence."""
        with self._lock:
            curr, ops, temps = Path(input_path), operations or [], []
            for i, op in enumerate(ops):
                op_t = op["op"]
                nxt = (
                    Path(output_path)
                    if (i == len(ops) - 1 and output_path)
                    else self._generate_output_path(curr, f"_step{i + 1}_{op_t}")
                )
                curr = getattr(self, op_t)(
                    curr, nxt, **{k: v for k, v in op.items() if k != "op"}
                )
                if nxt != Path(output_path or ""):
                    temps.append(curr)
            for t in temps:
                if t != curr:
                    try:
                        t.unlink()
                    except:
                        pass
            return curr

    def preprocess_for_transcription(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        silence_threshold_db: float = None,
        target_sample_rate: int = None,
    ) -> Path:
        """Apply silence trimming and downsampling for transcription."""
        ops = [
            {"op": "trim_silence", "threshold_db": silence_threshold_db},
            {"op": "downsample", "target_rate": target_sample_rate},
        ]
        return self.process_pipeline(input_path, output_path, ops)

    def convert_to_pcm(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path] = None,
        codec: str = "pcm_s16le",
        channels: int = 1,
        sample_rate: int = None,
    ) -> Path:
        """Convert audio to PCM format."""
        with self._lock:
            in_p = Path(input_path)
            if not in_p.exists():
                raise FileNotFoundError(f"Input file not found: {in_p}")
            if codec not in {"pcm_s16le", "pcm_s24le", "pcm_f32le"}:
                raise ValueError(f"Unsupported codec: {codec}")
            if not isinstance(channels, int) or channels <= 0:
                raise ValueError(f"channels must be a positive integer, got {channels}")
            if sample_rate and (not isinstance(sample_rate, int) or sample_rate <= 0):
                raise ValueError(
                    f"sample_rate must be a positive integer, got {sample_rate}"
                )

            out_p = (
                Path(output_path)
                if output_path
                else self._generate_output_path(in_p, f"_{codec}_{channels}ch")
            )
            args = {"acodec": codec, "ac": channels}
            if sample_rate:
                args["ar"] = sample_rate
            run_command(
                build_ffmpeg_command(str(in_p), str(out_p), codec_args=args),
                description="Audio PCM conversion",
            )
            return out_p

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
