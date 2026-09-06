"""Execute the local Sniper Pine decision/accounting subset on Forex Tester bars.

This is a deliberately narrow source bridge, not a general Pine interpreter.
TA primitives are implemented here; signal expressions and the price tracker are
read directly from the reviewed local Pine file. No downloaded code is executed.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

from .models import Bar


def is_na(value):
    return value is None or isinstance(value, float) and math.isnan(value)


def expression(text: str) -> str:
    """Translate nested Pine ternaries, preserving strings and parentheses."""
    text = text.strip()
    depth = 0
    question = None
    nesting = 0
    quoted = False
    escaped = False
    commas = []
    for i, ch in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            commas.append(i)
    if commas:
        boundaries = [-1, *commas, len(text)]
        return ", ".join(expression(text[a+1:b]) for a, b in zip(boundaries, boundaries[1:]))
    depth, quoted, escaped = 0, False, False
    for i, ch in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and ch == "?":
            if question is None:
                question = i
            nesting += 1
        elif depth == 0 and ch == ":" and question is not None:
            nesting -= 1
            if nesting == 0:
                return f"({expression(text[question+1:i])} if {expression(text[:question])} else {expression(text[i+1:])})"
    if question is not None:
        raise ValueError(f"Unsupported ternary: {text}")
    # Recursively translate bracket contents; quoted strings remain literal.
    tokens = re.split(r'("(?:\\.|[^"\\])*")', text)
    converted = []
    for token in tokens:
        if token.startswith('"'):
            converted.append(token)
            continue
        token = re.sub(r"\btrue\b", "True", token)
        token = re.sub(r"\bfalse\b", "False", token)
        token = re.sub(r"\bna\b(?!\s*\()", "NAN", token)
        # Only these two history references are present in f_engine.
        token = token.replace("longSetup[1]", "previousLong").replace("shortSetup[1]", "previousShort")
        converted.append(token)
    text = "".join(converted)
    out = ""
    i = 0
    while i < len(text):
        if text[i] == '"':
            match = re.match(r'"(?:\\.|[^"\\])*"', text[i:])
            assert match
            out += match[0]
            i += len(match[0])
        elif text[i] == "(":
            level, j = 1, i + 1
            while level:
                if text[j] == "(":
                    level += 1
                elif text[j] == ")":
                    level -= 1
                j += 1
            out += "(" + expression(text[i+1:j-1]) + ")"
            i = j
        else:
            out += text[i]
            i += 1
    return out


def translate(block: str) -> str:
    lines = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue
        indent = raw[:len(raw) - len(raw.lstrip())]
        stripped = re.sub(r"^(?:var )?(?:int|float|bool|string) ", "", stripped)
        if stripped.startswith("else if "):
            lines.append(indent + "elif " + expression(stripped[8:]) + ":")
        elif stripped.startswith("if "):
            lines.append(indent + "if " + expression(stripped[3:]) + ":")
        elif stripped == "else":
            lines.append(indent + "else:")
        else:
            match = re.match(r"(.+?) (:=|\+=|=) (.+)", stripped)
            if match:
                lhs, op, rhs = match.groups()
                lines.append(indent + lhs + " " + ("=" if op == ":=" else op) + " " + expression(rhs))
            elif stripped.startswith("["):
                # f_engine's final tuple is unused; values already live in the scope.
                continue
            else:
                lines.append(indent + expression(stripped))
    return "\n".join(lines) + "\n"


def method_from_source(source: str, name: str, arguments: str):
    match = re.search(rf"^method {name}\([^\n]+\) =>\n((?:    [^\n]*\n)+)", source, re.M)
    if not match:
        raise ValueError(f"Missing Pine method: {name}")
    namespace = {}
    exec(compile(f"def {name}({arguments}):\n" + translate(match[1]), "<local-pine-method>", "exec"), namespace)
    return namespace[name]


class RMA:
    def __init__(self, length):
        self.length, self.count, self.total, self.value = length, 0, 0.0, math.nan

    def update(self, value):
        if is_na(value):
            return self.value
        if self.count < self.length:
            self.count += 1
            self.total += value
            if self.count == self.length:
                self.value = self.total / self.length
        else:
            alpha = 1.0 / self.length
            self.value = alpha * value + (1 - alpha) * self.value
        return self.value


class Technicals:
    """Streaming EMA, Wilder ATR/RSI/DMI/ADX and TradingView-style Supertrend."""
    def __init__(self, config):
        self.config = config
        self.atr_ma = RMA(config["atrLength"])
        self.gain, self.loss = RMA(config["rsiLength"]), RMA(config["rsiLength"])
        self.tr, self.plus, self.minus = (RMA(config["dmiLength"]) for _ in range(3))
        self.dx = RMA(config["dmiLength"])
        self.previous = None
        self.e = self.a = self.r = self.p = self.m = self.adx = math.nan
        self.upper = self.lower = self.st = math.nan
        self.direction = 1

    def update(self, bar):
        previous = self.previous
        tr = bar.high - bar.low if previous is None else max(bar.high - bar.low, abs(bar.high - previous.close), abs(bar.low - previous.close))
        old_atr = self.a
        self.a = self.atr_ma.update(tr)
        alpha = 2.0 / (self.config["emaLength"] + 1)
        self.e = bar.close if is_na(self.e) else alpha * bar.close + (1 - alpha) * self.e
        change = math.nan if previous is None else bar.close - previous.close
        gain = self.gain.update(max(change, 0))
        loss = self.loss.update(max(-change, 0))
        self.r = math.nan if is_na(gain) or is_na(loss) or gain + loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
        up = math.nan if previous is None else bar.high - previous.high
        down = math.nan if previous is None else previous.low - bar.low
        plus = self.plus.update(math.nan if previous is None else up if up > down and up > 0 else 0.0)
        minus = self.minus.update(math.nan if previous is None else down if down > up and down > 0 else 0.0)
        tr_dmi = self.tr.update(math.nan if previous is None else tr)
        if not is_na(tr_dmi) and tr_dmi != 0:
            self.p, self.m = 100 * plus / tr_dmi, 100 * minus / tr_dmi
        total = self.p + self.m
        dx = abs(self.p - self.m) / (1 if total == 0 else total)
        self.adx = 100 * self.dx.update(dx)
        upper = (bar.high + bar.low) / 2 + self.config["stFactor"] * self.a
        lower = (bar.high + bar.low) / 2 - self.config["stFactor"] * self.a
        prior_upper = 0.0 if is_na(self.upper) else self.upper
        prior_lower = 0.0 if is_na(self.lower) else self.lower
        previous_close = math.nan if previous is None else previous.close
        lower = lower if lower > prior_lower or previous_close < prior_lower else prior_lower
        upper = upper if upper < prior_upper or previous_close > prior_upper else prior_upper
        if is_na(old_atr):
            self.direction = 1
        elif self.st == prior_upper:
            self.direction = -1 if bar.close > upper else 1
        else:
            self.direction = 1 if bar.close < lower else -1
        self.lower, self.upper = lower, upper
        self.st = lower if self.direction == -1 else upper
        self.previous = bar

    def atr(self, length):
        assert length == self.config["atrLength"]
        return self.a

    def ema(self, close, length):
        assert length == self.config["emaLength"]
        return self.e

    def rsi(self, close, length):
        assert length == self.config["rsiLength"]
        return self.r

    def supertrend(self, factor, length):
        assert (factor, length) == (self.config["stFactor"], self.config["atrLength"])
        return self.st, self.direction

    def dmi(self, length, smoothing):
        assert length == smoothing == self.config["dmiLength"]
        return self.p, self.m, self.adx


def pine_defaults(source):
    result = {}
    for name, kind, value in re.findall(r"^(?:int|float|bool) (\w+) = input\.(int|float|bool)\(([^,]+),", source, re.M):
        result[name] = value.strip() == "true" if kind == "bool" else int(value) if kind == "int" else float(value)
    return result


class Samples:
    def __init__(self, start, observe, owner):
        self._start, self._observe, self.owner = start, observe, owner
        self.wins = self.losses = self.pendingSide = 0
        self.rows = []

    def startSample(self, direction, signalBar, target, stopPrice):
        if self.pendingSide:
            raise AssertionError("Unresolved sample overwritten")
        self._start(self, direction, signalBar, target, stopPrice)
        env = self.owner.env
        self.rows.append(dict(entry_time=env["time_close"], direction=direction, entry=env["entry"], target=target, stop=stopPrice, outcome=None, exit_time=None, ambiguous=False))

    def observe(self, number, high, low):
        was_pending = self.pendingSide
        before = self.wins
        self._observe(self, number, high, low)
        if was_pending and not self.pendingSide:
            row = self.rows[-1]
            row["outcome"] = "win" if self.wins > before else "loss"
            row["exit_time"] = self.owner.env["time_close"]
            row["ambiguous"] = (high >= self.initialTarget and low <= self.initialStop) if was_pending == 1 else (low <= self.initialTarget and high >= self.initialStop)


class SniperReplay:
    """Read-only reuse of the current Pine defaults, signals, tracker and outcomes."""
    def __init__(self, source, tick_size, minutes=15, start_ms=0, end_ms=10**15):
        self.config = pine_defaults(source)
        self.ta = Technicals(self.config)
        self.minutes = minutes
        self.index = -1
        engine = re.search(r"^f_engine\(\) =>\n((?:    [^\n]*\n)+)", source, re.M)
        if not engine:
            raise ValueError("Missing Pine signal engine")
        engine_body = "\n".join(line[4:] for line in engine[1].splitlines())
        self.engine = compile(translate(engine_body), "<sniper-pine-engine>", "exec")
        initial = source.split("var int side = 0", 1)[1].split("bool buySignal = false", 1)[0]
        initial = "var int side = 0" + initial
        tracker = "bool buySignal = false" + source.split("bool buySignal = false", 1)[1].split("barcolor(", 1)[0]
        self.tracker = compile(translate(tracker), "<sniper-pine-tracker>", "exec")
        start_method = method_from_source(source, "startSample", "this, direction, signalBar, target, stopPrice")
        observe_method = method_from_source(source, "observe", "this, barNumber, barHigh, barLow")
        self.env = dict(self.config, NAN=math.nan, na=is_na, ta=self.ta,
                        previousLong=False, previousShort=False, barstate=SimpleNamespace(isconfirmed=True),
                        syminfo=SimpleNamespace(mintick=tick_size),
                        math=SimpleNamespace(max=max, min=min, abs=abs, round_to_mintick=lambda x: math.floor(x / tick_size + 0.5) * tick_size),
                        f_event=lambda *args: None, f_levels=lambda *args: None, f_extendLevels=lambda: None,
                        f_price=lambda x: str(x), color=SimpleNamespace(orange=0), buyColor=0, sellColor=0,
                        statsStart=start_ms, statsEnd=end_ms, sampledSignals=0, firstSampleTime=math.nan, lastSampleTime=math.nan)
        self.samples = [Samples(start_method, observe_method, self) for _ in range(3)]
        for index, sample in enumerate(self.samples, 1):
            self.env[f"tp{index}Stats"] = sample
        exec(compile(translate(initial), "<sniper-pine-initial-state>", "exec"), self.env)

    def update_signals(self, bar: Bar):
        """Advance causal Pine signals without imposing the display trade tracker."""
        self.index += 1
        self.ta.update(bar)
        # Forex Tester timestamps are used as stored, without broker-zone inference.
        stamp = int(((bar.time + timedelta(minutes=self.minutes)) - datetime(1970, 1, 1)).total_seconds() * 1000)
        env = self.env
        env.update(open=bar.open, high=bar.high, low=bar.low, close=bar.close, bar_index=self.index, time_close=stamp)
        exec(self.engine, env)
        env["previousLong"], env["previousShort"] = env["longSetup"], env["shortSetup"]
        env["atr"], env["signalEdge"] = env["a"], env["edge"]
        return env["edge"]

    def update(self, bar: Bar):
        self.update_signals(bar)
        env = self.env
        stamp = env["time_close"]
        if env["statsStart"] <= stamp <= env["statsEnd"]:
            for sample in self.samples:
                sample.observe(self.index, bar.high, bar.low)
        exec(self.tracker, env)
