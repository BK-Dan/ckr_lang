import re
from collections import defaultdict

# --- Constants & Configuration ---
CONSTANTS = {
    "부들부들": 0,
    "뾰족뾰족": -1,
    "폭신폭신": 1
}

START_MARKER = "흑백요리사2 히든백수저 최강록"
END_MARKER = "백수저 최강록 우승"

class CKRError(Exception):
    """Base class for CKR-Lang exceptions."""
    pass

class CKRRuntimeError(CKRError):
    """Runtime errors (e.g., modifying constants, undefined variables)."""
    pass

class CKRSyntaxError(CKRError):
    """Syntax errors (e.g., missing markers)."""
    pass

# --- 1. Lexer ---
class CKRLexer:
    """
    Handles source code cleaning and tokenization.
    - Removes comments (quoted strings, text outside markers).
    - Splits code into executable lines.
    """
    def clean_code(self, raw_code):
        # 1. Remove quoted strings (comments) - Handles both " and ' with multiline support
        # logic: match "..." or '...' and replace with empty string
        no_comment_code = re.sub(r'("[^"]*"|\'[^\']*\')', '', raw_code, flags=re.DOTALL)

        # 2. Extract code between markers
        try:
            start_idx = no_comment_code.index(START_MARKER) + len(START_MARKER)
            end_idx = no_comment_code.index(END_MARKER)
            if start_idx >= end_idx:
                raise ValueError("Start marker appears after end marker.")
            core_code = no_comment_code[start_idx:end_idx]
        except ValueError:
            raise CKRSyntaxError("이 요리는 시작되거나 끝날 수 없습니다. (시작/종료 구문 확인)")

        return core_code

    def tokenize(self, raw_code):
        core_code = self.clean_code(raw_code)
        
        # Suffix keywords that end a command
        # Note: "조림인간/욕망의조림인간" are part of "조림핑" construct, usually appearing before "조림핑". 
        # But "조림핑" is the strict command ender.
        SUFFIX_KEYWORDS = {"조려", "조린다", "조리고", "앙", "을", "조림핑"}
        PREFIX_KEYWORD = "나야"
        
        # Flatten the entire code into a single stream of tokens
        all_tokens = core_code.split()
        
        grouped_instructions = []
        buffer = []
        
        for i, token in enumerate(all_tokens):
            
            # Case 0: Label Definition (startswith '연쇄조림마') -> Acts as a separator
            if token.startswith("연쇄조림마"):
                 if buffer:
                     # Check for leftover buffer (e.g. '나야 A B')
                     grouped_instructions.append(buffer)
                     buffer = []
                 grouped_instructions.append([token])
                 continue

            # Case 1: Token is '나야' -> Start of Command
            if token == PREFIX_KEYWORD:
                if buffer: 
                    # If we have a previous unfinished buffer, flush it.
                    # This happens if we have '나야 A B' then '나야 C D'
                    grouped_instructions.append(buffer)
                buffer = [token]
                
            # Case 2: Token is a Suffix -> End of Command
            elif token in SUFFIX_KEYWORDS or token.startswith("조림핑"):
                buffer.append(token)
                
                # COLLISION CHECK: If buffer started with '나야' and now ends with Suffix.
                if buffer[0] == PREFIX_KEYWORD:
                     # Buffer: [나야, arg1, arg2, ..., argN, Suffix]
                     # We need to find where '나야' ends. 
                     # Heuristic: '나야' consumes tokens until it finds one WITHOUT a comma.
                     # Because CKR lists MUST be comma-separated. The last item of a list has no comma.
                     
                     na_ya_args = []
                     suffix_args = []
                     
                     args = buffer[1:-1]
                     split_idx = -1
                     
                     for idx, arg in enumerate(args):
                         na_ya_args.append(arg)
                         if not arg.endswith(","):
                             split_idx = idx
                             break
                     
                     if split_idx != -1 and split_idx < len(args) - 1:
                         # We found a split point, and there are leftover args for the Suffix
                         suffix_args = args[split_idx+1:]
                         
                         cmd1 = [PREFIX_KEYWORD] + na_ya_args
                         grouped_instructions.append(cmd1)
                         
                         cmd2 = suffix_args + [token]
                         grouped_instructions.append(cmd2)
                     else:
                         # No split point found (all had commas?) or no leftovers.
                         # Assume all belong to '나야' (invalid syntax generally if Suffix is there, but let parser fail)
                         # OR, maybe '나야' consumes everything and Suffix applies to the last one?
                         # Actually, if we have [나야, A, B, 조려], and A has no comma.
                         # Split at A. cmd1=[나야, A]. cmd2=[B, 조려]. 
                         # If [나야, A, 조려]. Split at A. cmd1=[나야, A]. cmd2=[조려] (Invalid? Suffix needs target).
                         # But let's stick to the split rule.
                         if split_idx != -1: # Found a split
                             cmd1 = [PREFIX_KEYWORD] + na_ya_args
                             cmd2 = suffix_args + [token] # suffix_args is empty here
                             grouped_instructions.append(cmd1)
                             grouped_instructions.append(cmd2)
                         else:
                             # Fallback: Just dump the whole buffer? 
                             # If we have [나야, A, B, 조려] and ALL have commas? 
                             # Then '나야' takes A,B. '조려' takes... nothing?
                             grouped_instructions.append(buffer)
                else:
                    # Normal Suffix command
                    grouped_instructions.append(buffer)
                
                buffer = []
                
            # Case 3: Token is argument/variable
            else:
                buffer.append(token)
        
        # Flush remaining buffer (e.g. '나야 A B' at end of file)
        if buffer:
            grouped_instructions.append(buffer)
            
        return grouped_instructions

# --- 2. Parser ---
class CKRParser:
    """
    Parses tokenized instruction lists into objects.
    """
    def parse(self, instruction_groups):
        instructions = []
        labels = {}
        
        for tokens in instruction_groups:
            if not tokens:
                continue
            
            line_str = " ".join(tokens)
            
            # Label Handling: "연쇄조림마..."
            if tokens[0].startswith("연쇄조림마"):
                dots = tokens[0].replace("연쇄조림마", "").strip()
                labels[dots] = len(instructions) 
                continue

            # Instruction Parsing
            instructions.append({'line': line_str, 'tokens': tokens})
            
        return instructions, labels

# --- 3. Evaluator ---
class CKREvaluator:
    """
    Runtime environment for CKR-Lang.
    """
    def __init__(self, debug=False):
        self.variables = defaultdict(int) # Default 0
        self.debug = debug
        self.pc = 0

    def get_val(self, name):
        if name in CONSTANTS:
            return CONSTANTS[name]
        if name in self.variables:
            return self.variables[name]
        raise CKRRuntimeError(f"재료 '{name}'가 손질되지 않았습니다. (변수 미선언)")

    def set_val(self, name, value):
        if name in CONSTANTS:
            raise CKRRuntimeError(f"'{name}'은(는) 이미 완벽한 상태라 조리할 수 없습니다. (상수 변경 불가)")
        self.variables[name] = value

    def check_mutable(self, name):
        if name in CONSTANTS:
            raise CKRRuntimeError(f"'{name}'은(는) 이미 완벽한 상태라 조리할 수 없습니다. (상수 변경 불가)")

    def parse_subjects(self, subject_chunk):
        # "민물장어, 두부" -> ["민물장어", "두부"]
        if not subject_chunk: return []
        return [s.strip() for s in subject_chunk.split(",") if s.strip()]

    def run(self, instructions, labels):
        self.pc = 0
        while self.pc < len(instructions):
            inst = instructions[self.pc]
            line = inst['line']
            tokens = inst['tokens']
            # --- Command Parsing ---
            if tokens[0] == "나야":
                cmd = "나야"
            else:
                cmd = tokens[-1] # Valid CKR commands are always at the end

            if self.debug:
                print(f"[DEBUG] PC:{self.pc:03d} | CMD:{cmd} | VARS:{dict(self.variables)}")

            # --- Control Flow ---
            if "조림핑" in cmd:
                target_dots = cmd.replace("조림핑", "")
                
                # Check for Conditions
                condition_met = True
                if len(tokens) >= 2 and ("조림인간" in tokens[-2] or "욕망의조림인간" in tokens[-2]):
                    cond_op = tokens[-2]
                    subjects = self.parse_subjects(" ".join(tokens[:-2]))
                    values = [self.get_val(s) for s in subjects]
                    
                    if not values: # Should not happen based on partial syntax, but safe check
                        condition_met = False
                    elif cond_op == "조림인간": # IF = (All Zero or All Equal)
                         if len(values) == 1: condition_met = (values[0] == 0)
                         else: condition_met = all(v == values[0] for v in values)
                    elif cond_op == "욕망의조림인간": # IF > (First > All others)
                        if len(values) == 1: condition_met = (values[0] > 0)
                        else:
                            base = values[0]
                            condition_met = all(base > v for v in values[1:])
                
                if condition_met:
                    if target_dots not in labels:
                        raise CKRRuntimeError(f"갈 곳이 없다. '{target_dots}' 라벨을 찾을 수 없음.")
                    self.pc = labels[target_dots]
                    continue # Jump immediately

            # --- Operations ---
            else:
                if cmd == "나야":
                     subjects = self.parse_subjects(" ".join(tokens[1:]))
                else:
                     subjects = self.parse_subjects(" ".join(tokens[:-1]))
                
                if cmd == "나야": # SET
                    for s in subjects:
                        self.check_mutable(s)
                        self.variables[s] = 0
                        
                elif cmd == "조려": # ADD
                    if subjects:
                        target = subjects[0]
                        self.check_mutable(target)
                        if len(subjects) == 1:
                            self.variables[target] += 1
                        else:
                            # Sum all values
                            total = sum(self.get_val(s) for s in subjects)
                            self.variables[target] = total

                elif cmd == "조린다": # SUB
                    if subjects:
                        target = subjects[0]
                        self.check_mutable(target)
                        if len(subjects) == 1:
                            self.variables[target] -= 1
                        else:
                            first = self.get_val(subjects[0])
                            others = sum(self.get_val(s) for s in subjects[1:])
                            self.variables[target] = first - others

                elif cmd == "조리고": # MUL
                    if subjects:
                        target = subjects[0]
                        self.check_mutable(target)
                        if len(subjects) == 1:
                            self.variables[target] *= 2
                        else:
                            res = 1
                            for s in subjects: res *= self.get_val(s)
                            self.variables[target] = res

                elif cmd == "앙": # INVERSE
                    for s in subjects:
                        self.check_mutable(s)
                        self.variables[s] = -self.variables[s]

                elif cmd == "을": # PRINT
                    for s in subjects:
                        val = self.get_val(s)
                        try:
                            # Convert to char if possible, else '?' or raw? Spec says ASCII char.
                            # Python's chr() works for unicode too, which is good for coverage.
                            # Standard ASCII is 0-127, but we'll allow full unicode range safe.
                            print(chr(val), end="") 
                        except ValueError:
                            print("?", end="")
                
                else:
                    # Generic error for unknown command
                    raise CKRRuntimeError(f"알 수 없는 조리법입니다: {cmd}")

            self.pc += 1
