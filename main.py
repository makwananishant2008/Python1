"""
PTMAE - Pure Python Transactional Micro-Banking & Audit Engine
Document ID: PTMAE-SRS-1.0   (Python Programming, Units 1-5)

Only the allowed module `datetime` is imported (random is allowed but not needed).
Run:  python main.py
"""

import datetime  # allowed module (SRS 5.1) - used only for ledger / log timestamps

# ======================================================================
# SECTION 0 - SMALL SHARED HELPERS
# ======================================================================

PROMPT = "ptmae> "                               # text shown before every command
TERMINATE_FLAG = "TERMINATE"                     # special marker used by the trajectory guard
VALID_TYPES = ("SAVINGS", "CURRENT", "CREDIT")   # account types allowed in accounts.db
DB_FILE = "accounts.db"                          # the plain-text database
LEDGER_FILE = "ledger.txt"                       # accepted updates are appended here
CORRUPTED_LOG = "corrupted.log"                  # rejected records are appended here


def timestamp():
    """Return the current date and time as a readable string (uses datetime)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_finite_number(value):
    """Convert text/number to float; raise ValueError for words, nan and inf."""
    number = float(value)                 # float() raises ValueError for words like "abc"
    if number != number or number - number != 0:   # nan != nan ; inf - inf is nan (not 0)
        raise ValueError("number is not finite")
    return number


def banner(title):
    """Print a heading so the demonstration output is easy to read."""
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ======================================================================
# SECTION 1 - MODULE 1: STATE CONTROL ENGINE AND TRAJECTORY GUARDS (Unit 1)
# ======================================================================

def compound_interest(principal, rate_percent, years):
    """FR-1.2: final amount after compounding yearly. Uses only * / + - in a loop."""
    amount = principal                              # start with the money we deposit
    year = 0                                        # loop counter
    while year < years:                             # repeat once per year
        amount = amount * (1 + rate_percent / 100)  # add one year of interest
        year = year + 1                             # move to next year
    return amount


def penalty_fee(amount, days_overdue, rate_percent=2.0):
    """FR-1.2: penalty for late payment. 2% per full 30-day block (compounding)
    plus a pro-rata part for the leftover days. Uses // and % and loops only."""
    blocks = days_overdue // 30             # // = whole 30-day blocks
    leftover_days = days_overdue % 30       # % = days that do not fill a block
    running = amount                        # amount grows after each block
    block = 0
    while block < blocks:
        running = running + running * rate_percent / 100   # add 2% of current amount
        block = block + 1
    fee = running - amount                  # fee so far = growth in whole blocks
    fee = fee + running * rate_percent / 100 * leftover_days / 30   # pro-rata part
    return fee


def trajectory_guard(start_balance, transactions, threshold):
    """FR-1.3: walk through transactions; stop at once if
       (a) the TERMINATE flag is met, or (b) balance < threshold.
    Returns (final_balance, reason_text, number_of_transactions_applied)."""
    balance = start_balance
    applied = 0
    for position, tx in enumerate(transactions):
        # Short-circuit `or`: if tx is the flag, Python never evaluates the
        # second part, so we never compare/add a string with numbers.
        if tx == TERMINATE_FLAG or balance < threshold:
            if tx == TERMINATE_FLAG:
                reason = "halted: termination flag at position " + str(position)
            else:
                reason = "halted: balance " + str(balance) + " fell below " + str(threshold)
            return balance, reason, applied
        balance = balance + tx              # apply the transaction
        applied = applied + 1
    # loop ended normally; do a last check because the last tx may have broken the limit
    if balance < threshold:
        return balance, "halted: balance " + str(balance) + " fell below " + str(threshold), applied
    return balance, "completed: all transactions applied", applied


def tokenize_command(line):
    """Cut a command line into words using our own parser (space = delimiter)."""
    tokens = parse_raw_log_line(line, " ")
    words = []
    for token in tokens:
        if token != "":                     # ignore empty pieces from double spaces
            words.append(token)
    return words


HELP_TEXT = (
    "Commands:\n"
    "  interest <principal> <rate%> <years>      e.g. interest 1000 10 3\n"
    "  penalty  <amount> <days_overdue>          e.g. penalty 1000 45\n"
    "  guard    <start> <threshold> <tx...>      e.g. guard 500 100 -200 -250 TERMINATE\n"
    "  parse    <csv line>                       e.g. parse a,\"b,c\",d\n"
    "  help                                      show this list\n"
    "  exit                                      leave the program"
)


def execute_command(line):
    """Run one command line and return the text to show the operator.
    Bad input raises ValueError, which the event loop catches (NFR-1)."""
    words = tokenize_command(line)
    command = words[0].lower()
    if command == "help":
        return HELP_TEXT
    if command == "interest":
        if len(words) != 4:
            raise ValueError("usage: interest <principal> <rate%> <years>")
        principal = to_finite_number(words[1])
        rate = to_finite_number(words[2])
        years = int(words[3])               # int() raises ValueError for "2.5" / words
        if principal < 0 or rate < 0 or years < 0:
            raise ValueError("values must not be negative")
        final = compound_interest(principal, rate, years)
        return "Final amount: " + format(final, ".2f") + "  (interest " + format(final - principal, ".2f") + ")"
    if command == "penalty":
        if len(words) != 3:
            raise ValueError("usage: penalty <amount> <days_overdue>")
        amount = to_finite_number(words[1])
        days = int(words[2])
        if amount < 0 or days < 0:
            raise ValueError("values must not be negative")
        return "Penalty fee: " + format(penalty_fee(amount, days), ".2f")
    if command == "guard":
        if len(words) < 4:
            raise ValueError("usage: guard <start> <threshold> <tx...>")
        start = to_finite_number(words[1])
        threshold = to_finite_number(words[2])
        txs = []
        for word in words[3:]:              # slice = every word after the first three
            if word.upper() == TERMINATE_FLAG:
                txs.append(TERMINATE_FLAG)
            else:
                txs.append(to_finite_number(word))
        final, reason, applied = trajectory_guard(start, txs, threshold)
        return "Balance " + format(final, ".2f") + " after " + str(applied) + " transaction(s) - " + reason
    if command == "parse":
        rest = line[len("parse"):]          # slice off the word "parse"
        if rest[:1] == " ":
            rest = rest[1:]                 # drop the single space after it
        return "Tokens: " + repr(parse_raw_log_line(rest))
    raise ValueError("unknown command '" + words[0] + "' (type help)")


def run_cli(scripted_commands=None):
    """FR-1.1: interactive event loop made of NESTED while loops.
    Outer loop = one pass per command. Inner loop = keep asking until the line
    is not blank. Only the command 'exit' ends the outer loop.
    If `scripted_commands` (a list) is given, they are used instead of input()."""
    next_item = 0                           # index into the scripted list
    running = True
    while running:                          # OUTER loop: the session
        line = ""
        while line == "":                   # INNER loop: ignore blank lines
            if scripted_commands is not None:
                if next_item >= len(scripted_commands):
                    line = "exit"           # script finished -> leave cleanly
                else:
                    line = scripted_commands[next_item].strip()
                    next_item = next_item + 1
                    print(PROMPT + line)
            else:
                try:
                    line = input(PROMPT).strip()
                except EOFError:            # Ctrl-D / closed input: exit politely
                    line = "exit"
        if line.lower() == "exit":
            print("Goodbye.")
            running = False                 # the ONLY way out of the outer loop
        else:
            try:
                print(execute_command(line))
            except ValueError as err:       # invalid input never crashes the loop
                print("Error: " + str(err))


# ======================================================================
# SECTION 2 - MODULE 2: NATIVE LOG PARSER AND CLOSURE MECHANICS (Unit 2)
# ======================================================================

def parse_raw_log_line(line, delimiter=",", quote_char='"'):
    """FR-2.1: hand-written CSV-style parser. Works index by index with state flags.
    - delimiter inside quotes is data           (FR-2.1.2)
    - doubled quote inside quotes -> one quote   (FR-2.1.3)
    - empty fields and trailing delimiter kept   (FR-2.1.4)
    Raises ValueError if a quote is never closed."""
    tokens = []             # finished fields
    current = ""            # field being built
    in_quotes = False       # state flag: are we inside "...."?
    was_quoted = False      # state flag: did this field use quotes? (then keep spaces)
    index = 0               # position in the line
    length = len(line)
    while index < length:
        char = line[index]                          # look at one character
        if in_quotes:
            if char == quote_char:
                if line[index + 1:index + 2] == quote_char:   # slice peeks at next char
                    current = current + quote_char  # "" -> one literal quote
                    index = index + 2               # skip both quote characters
                    continue
                in_quotes = False                   # a single quote closes the field part
            else:
                current = current + char            # normal data (even a delimiter)
        else:
            if char == quote_char:
                in_quotes = True                    # opening quote
                was_quoted = True
            elif char == delimiter:
                if not was_quoted:
                    current = current.strip()       # clean unquoted token
                tokens.append(current)              # field finished
                current = ""
                was_quoted = False
            else:
                current = current + char
        index = index + 1
    if in_quotes:
        raise ValueError("unterminated quoted field")
    if not was_quoted:
        current = current.strip()
    tokens.append(current)      # last field (an empty string if line ended with delimiter)
    return tokens


def create_audit_filter(threshold):
    """FR-2.2: return a validation function that remembers how many records it audited.
    `count` lives in the enclosing scope and is changed with `nonlocal`.
    Each call of create_audit_filter makes its OWN independent count."""
    count = 0

    def validate(amount):
        """Return True when amount >= threshold; always increase the audit counter."""
        nonlocal count                  # we want to change the outer variable
        count = count + 1
        return amount >= threshold

    def audited_count():
        """Read the current number of audited records."""
        return count

    validate.audited_count = audited_count   # attach the reader to the function object
    return validate


def build_positional_filters(position_count):
    """FR-2.3: build a list of lambdas; lambda number k filters by position k.
    `k=k` freezes the loop value at definition time (avoids late binding)."""
    filters = []
    for k in range(position_count):
        filters.append(lambda transactions, wanted, k=k: [t for t in transactions if t[k] == wanted])
    return filters


def build_positional_filters_buggy(position_count):
    """Teaching example ONLY: without k=k every lambda sees the LAST k (late binding)."""
    filters = []
    for k in range(position_count):
        filters.append(lambda transactions, wanted: [t for t in transactions if t[k] == wanted])
    return filters


# ======================================================================
# SECTION 3 - MODULE 3: DATA INVERSION AND IN-PLACE PROCESSING (Unit 3)
# ======================================================================

def invert_services(raw_db):
    """FR-3.1: one dict comprehension builds {service_tag: sorted unique [(Account_ID, Branch_ID)]}.
    Outer set comprehension collects every tag; the inner set comprehension collects
    the (account, branch) pairs that own that tag; sorted() makes it alphabetical."""
    return {
        tag: sorted({(account, branch)
                     for branch, entries in raw_db.items()
                     for account, tags in entries
                     if tag in tags})
        for tag in {t for entries in raw_db.values() for _, tags in entries for t in tags}
    }


def clean_transaction_queue(data_list):
    """FR-3.2: clean a mixed list IN PLACE (same list object, never rebinding data_list).
    1) tuple -> list   2) set: remove even IDs (set difference)
    3) every embedded list sorted descending   4) remove duplicate primitives, keep first,
       by scanning the list itself and deleting by index (no extra collection)."""
    for index in range(len(data_list)):
        element = data_list[index]
        if isinstance(element, tuple):
            data_list[index] = list(element)        # item assignment mutates the SAME list
            element = data_list[index]
        if isinstance(element, set):
            evens = {x for x in element if isinstance(x, int) and x % 2 == 0}  # short-lived temp
            element -= evens                        # set difference, done in place
        elif isinstance(element, list):
            element.sort(reverse=True)              # descending
    # duplicate removal: compare each primitive with the ones after it
    first = 0
    while first < len(data_list):
        keeper = data_list[first]
        if isinstance(keeper, (int, float, str, bool)):
            probe = first + 1
            while probe < len(data_list):
                other = data_list[probe]
                if type(other) is type(keeper) and other == keeper:
                    del data_list[probe]            # delete by index; do NOT move probe
                else:
                    probe = probe + 1
        first = first + 1


# ======================================================================
# SECTION 4 - MODULE 4: TRANSACTIONAL FILE MODIFIER AND ERROR LOGGER (Unit 4)
# ======================================================================

class BaseSystemError(Exception):
    """FR-4.1: parent of every PTMAE error; catching it catches all three below."""


class CorruptedRecordError(BaseSystemError):
    """A database line is malformed (wrong field count, bad number, unknown type)."""


class OutOfBoundsError(BaseSystemError):
    """A value is outside the allowed range (bad amount, limit exceeded)."""


class InsufficientBalanceError(BaseSystemError):
    """The account does not have enough money for the requested transaction."""


def validate_record(line):
    """Check one accounts.db line. Return (account_id, account_type, balance)
    or raise CorruptedRecordError. Records must be plain ASCII (keeps byte offsets exact)."""
    text = line.rstrip("\r\n")
    for char in text:
        if ord(char) > 127:
            raise CorruptedRecordError("non-ASCII character in record")
    try:
        fields = parse_raw_log_line(text)
    except ValueError as err:
        raise CorruptedRecordError(str(err))
    if len(fields) != 3:
        raise CorruptedRecordError("expected 3 fields but found " + str(len(fields)))
    account_id, account_type, balance_text = fields
    if account_id == "":
        raise CorruptedRecordError("empty account id")
    if account_type not in VALID_TYPES:
        raise CorruptedRecordError("unknown account type '" + account_type + "'")
    try:
        balance = to_finite_number(balance_text)
    except ValueError:
        raise CorruptedRecordError("non-numeric balance '" + balance_text + "'")
    return account_id, account_type, balance


def validate_update(account_type, new_balance):
    """Check a requested new balance. Returns it as float or raises OutOfBoundsError."""
    try:
        value = to_finite_number(new_balance)
    except (ValueError, TypeError):
        raise OutOfBoundsError("new balance is not a valid number")
    if value > 10 ** 12 or value < -(10 ** 12):
        raise OutOfBoundsError("new balance outside +/- 1 trillion")
    if account_type == "SAVINGS" and value < 0:
        raise OutOfBoundsError("a SAVINGS balance cannot be negative")
    return value


def format_record(account_id, account_type, balance):
    """Build the text of one database record (without line ending)."""
    return account_id + "," + account_type + "," + format(balance, ".2f")


def log_corrupted(line_number, reason, raw_text):
    """FR-4.3.1: append one entry to corrupted.log (with the line number)."""
    with open(CORRUPTED_LOG, "a", encoding="utf-8") as log:      # NFR-3: with statement
        log.write(timestamp() + " | line " + str(line_number) + " | " + reason
                  + " | " + raw_text.rstrip("\r\n") + "\n")


def write_ledger(account_id, account_type, old_balance, new_balance):
    """FR-4.3.2: append one entry to ledger.txt for an accepted update."""
    with open(LEDGER_FILE, "a", encoding="utf-8") as ledger:
        ledger.write(timestamp() + " | " + account_id + " | " + account_type + " | "
                     + format(old_balance, ".2f") + " -> " + format(new_balance, ".2f") + "\n")


def rewrite_line_in_place(f, start, old_length, new_line, chunk_size=64):
    """FR-4.2: replace the line that begins at offset `start` (old_length characters)
    by `new_line`, WITHOUT reading/rewriting the whole file.
    - same length : just overwrite
    - shorter     : write new line, copy the tail LEFT chunk by chunk, truncate()
    - longer      : copy the tail RIGHT chunk by chunk (from the end backwards), write new line
    Afterwards the file pointer is placed right after the new line."""
    new_length = len(new_line)
    delta = new_length - old_length
    tail_start = start + old_length                 # where the untouched part begins
    if delta == 0:
        f.seek(start)
        f.write(new_line)
    elif delta < 0:                                 # record got shorter
        f.seek(start)
        f.write(new_line)
        read_pos = tail_start
        write_pos = start + new_length
        while True:
            f.seek(read_pos)
            chunk = f.read(chunk_size)
            if chunk == "":
                break                               # reached end of file
            f.seek(write_pos)
            f.write(chunk)
            read_pos = read_pos + len(chunk)
            write_pos = write_pos + len(chunk)
        f.seek(write_pos)
        f.truncate()                                # cut the leftover old bytes at the end
    else:                                           # record got longer
        f.seek(0, 2)                                # whence=2 -> go to the end of file
        pos = f.tell()                              # end of file
        while pos > tail_start:
            chunk_start = pos - chunk_size
            if chunk_start < tail_start:
                chunk_start = tail_start            # do not go before the tail
            f.seek(chunk_start)
            chunk = f.read(pos - chunk_start)
            f.seek(chunk_start + delta)             # move it `delta` characters to the right
            f.write(chunk)
            pos = chunk_start
        f.seek(start)
        f.write(new_line)
    f.seek(start + new_length)                      # continue scanning after this record


def process_account_updates(path, updates, chunk_size=64):
    """FR-4.2/4.3: scan `path`, validate every record, apply `updates`
    ({account_id: new_balance}) in place, log problems and report counts.
    Returns a dict with processed / updated / rejected counts."""
    counts = {"processed": 0, "updated": 0, "rejected": 0}
    seen_ids = []
    line_number = 0
    try:                                            # ---- try
        with open(path, "r+", encoding="utf-8", newline="") as f:   # r+ = read AND write
            while True:
                start = f.tell()                    # where this line starts
                line = f.readline()
                if line == "":
                    break                           # end of file
                line_number = line_number + 1
                try:                                # per-record try/except/else
                    account_id, account_type, balance = validate_record(line)
                except CorruptedRecordError as err:
                    counts["rejected"] += 1
                    log_corrupted(line_number, str(err), line)
                else:
                    counts["processed"] += 1
                    if account_id in updates:
                        if account_id not in seen_ids:
                            seen_ids.append(account_id)
                        try:
                            new_balance = validate_update(account_type, updates[account_id])
                        except BaseSystemError as err:
                            counts["rejected"] += 1
                            log_corrupted(line_number, "update rejected: " + str(err), line)
                        else:
                            ending = line[len(line.rstrip("\r\n")):]   # keep original newline
                            new_line = format_record(account_id, account_type, new_balance) + ending
                            rewrite_line_in_place(f, start, len(line), new_line, chunk_size)
                            write_ledger(account_id, account_type, balance, new_balance)
                            counts["updated"] += 1
        for wanted in updates:                      # ids that never appeared in the file
            if wanted not in seen_ids:
                counts["rejected"] += 1
                log_corrupted(0, "update rejected: account '" + wanted + "' not found", "")
    except OSError as err:                          # ---- except (file problems)
        print("File error: " + str(err))
    except Exception as err:                        # NFR-1: never crash on surprises
        print("Unexpected error: " + str(err))
    else:                                           # ---- else (no exception happened)
        print("File processing finished without errors.")
    finally:                                        # ---- finally: runs ALWAYS (FR-4.3.3)
        print("Report -> processed: " + str(counts["processed"])
              + ", updated: " + str(counts["updated"])
              + ", rejected: " + str(counts["rejected"]))
    return counts


# ======================================================================
# SECTION 5 - MODULE 5: OOP ARCHITECTURE AND POLYMORPHIC ENGINE (Unit 5)
# ======================================================================

class Account:
    """FR-5.1: base class. __balance is PRIVATE (name-mangled), _account_id is
    PROTECTED (convention), total_accounts is a CLASS attribute shared by all."""

    total_accounts = 0                              # class attribute

    def __init__(self, account_id, balance=0):
        """Create an account; the setters validate the inputs."""
        self._account_id = None                     # protected attribute
        self.__balance = 0                          # private -> stored as _Account__balance
        self.set_account_id(account_id)
        self.set_balance(balance)
        Account.total_accounts += 1

    def get_account_id(self):
        """Public getter for the protected id."""
        return self._account_id

    def set_account_id(self, account_id):
        """Public setter: id must be a non-empty string, else raise."""
        if not isinstance(account_id, str):
            raise TypeError("account id must be a string")
        if account_id.strip() == "":
            raise OutOfBoundsError("account id must not be empty")
        self._account_id = account_id

    def get_balance(self):
        """Public getter for the private balance."""
        return self.__balance

    def set_balance(self, value):
        """Public setter: balance must be a finite number (bool is not accepted)."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("balance must be a number")
        if value != value or value - value != 0:
            raise OutOfBoundsError("balance must be finite")
        self.__balance = value

    def _validate_amount(self, amount):
        """Protected helper used by subclasses: amount must be a positive finite number."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("amount must be a number")
        if amount != amount or amount - amount != 0 or amount <= 0:
            raise OutOfBoundsError("amount must be a positive finite number")

    def process_settlement(self, amount):
        """Overridden by every subclass (polymorphism)."""
        raise NotImplementedError("subclasses must implement process_settlement")


class SavingsAccount(Account):
    """Savings: the balance may never drop below 1000 after a settlement."""

    MINIMUM_BALANCE = 1000

    def __init__(self, account_id, balance=0):
        """Initialise through super() - no hard-coded base-class name."""
        super().__init__(account_id, balance)

    def process_settlement(self, amount):
        """Reject if remaining balance < 1000, otherwise deduct."""
        self._validate_amount(amount)
        remaining = self.get_balance() - amount
        if remaining < self.MINIMUM_BALANCE:
            raise InsufficientBalanceError("savings must keep at least " + str(self.MINIMUM_BALANCE))
        self.set_balance(remaining)
        return remaining


class CurrentAccount(Account):
    """Current: balance may go negative up to a private overdraft limit."""

    def __init__(self, account_id, balance=0, overdraft_limit=5000):
        """Initialise via super(), then store the private overdraft limit."""
        super().__init__(account_id, balance)
        if isinstance(overdraft_limit, bool) or not isinstance(overdraft_limit, (int, float)) or overdraft_limit < 0:
            raise OutOfBoundsError("overdraft limit must be a non-negative number")
        self.__overdraft_limit = overdraft_limit    # -> _CurrentAccount__overdraft_limit

    def get_overdraft_limit(self):
        """Public getter for the private overdraft limit."""
        return self.__overdraft_limit

    def process_settlement(self, amount):
        """Allow the balance to fall to -overdraft_limit, not lower."""
        self._validate_amount(amount)
        remaining = self.get_balance() - amount
        if remaining < -self.__overdraft_limit:
            raise InsufficientBalanceError("overdraft limit of " + str(self.__overdraft_limit) + " exceeded")
        self.set_balance(remaining)
        return remaining


class CreditAccount(Account):
    """Credit: balance = available credit. Each settlement costs amount + 2.5% surcharge."""

    SURCHARGE_RATE = 0.025

    def __init__(self, account_id, credit_limit=0):
        """Initialise via super(); available credit starts at the full limit."""
        super().__init__(account_id, credit_limit)
        if credit_limit < 0:
            raise OutOfBoundsError("credit limit must not be negative")
        self.__credit_limit = credit_limit

    def get_credit_limit(self):
        """Public getter for the private credit limit."""
        return self.__credit_limit

    def process_settlement(self, amount):
        """Add 2.5% surcharge, then deduct from available credit."""
        self._validate_amount(amount)
        total = amount + amount * self.SURCHARGE_RATE
        if total > self.get_balance():
            raise OutOfBoundsError("amount + surcharge " + format(total, ".2f") + " exceeds available credit")
        self.set_balance(self.get_balance() - total)
        return self.get_balance()


def execute_batch_settlement(account_list, transaction_amount):
    """FR-5.3: settle every account polymorphically. EACH call has its own
    try/except so one failure never stops the rest. Returns (successes, failures)."""
    successes = []
    failures = []
    for account in account_list:
        try:
            new_balance = account.process_settlement(transaction_amount)   # polymorphic call
        except BaseSystemError as err:               # expected business rejections
            failures.append((account.get_account_id(), type(err).__name__ + ": " + str(err)))
        except Exception as err:                     # anything unexpected is still isolated
            failures.append((account.get_account_id(), "Unexpected " + type(err).__name__ + ": " + str(err)))
        else:
            successes.append((account.get_account_id(), new_balance))
    print("Batch settlement of " + str(transaction_amount) + ": "
          + str(len(successes)) + " succeeded, " + str(len(failures)) + " failed")
    for account_id, balance in successes:
        print("  OK   " + account_id + " -> balance " + format(balance, ".2f"))
    for account_id, reason in failures:
        print("  FAIL " + account_id + " -> " + reason)
    return successes, failures


# ======================================================================
# SECTION 6 - DEMONSTRATIONS (NFR-6: exercise every FR)
# ======================================================================

def close_enough(a, b):
    """True when two floats match within 0.000001."""
    return abs(a - b) < 0.000001


def demo_module_1():
    """Demonstrate FR-1.1, FR-1.2, FR-1.3."""
    banner("MODULE 1 - State engine (FR-1.1 / 1.2 / 1.3)")
    print("FR-1.2 hand-calculation checks (loop result vs. ** formula):")
    for principal, rate, years, hand in ((1000, 10, 3, 1331.00), (5000, 6, 2, 5618.00)):
        loop_value = compound_interest(principal, rate, years)
        formula = principal * (1 + rate / 100) ** years
        print("  interest", principal, rate, years, "-> loop", format(loop_value, ".4f"),
              "| formula", format(formula, ".4f"), "| hand", hand,
              "| match:", close_enough(loop_value, hand) and close_enough(formula, hand))
    for amount, days, hand in ((1000, 45, 30.2), (2000, 65, 87.736)):
        fee = penalty_fee(amount, days)
        print("  penalty", amount, days, "->", format(fee, ".4f"), "| hand", hand,
              "| match:", close_enough(fee, hand))
    print("FR-1.3 trajectory guard:")
    print("  flag stop     :", trajectory_guard(500, [-50, 100, TERMINATE_FLAG, 999], 100))
    print("  threshold stop:", trajectory_guard(500, [-200, -250, 300], 100))
    print("FR-1.1 event loop (scripted; valid, invalid, blank, then exit):")
    run_cli(["help", "interest 1000 10 3", "dance", "", "penalty abc 10", "guard 500 100 -50 -20 TERMINATE 999", "exit"])


def demo_module_2():
    """Demonstrate FR-2.1.x, FR-2.2, FR-2.3."""
    banner("MODULE 2 - Parser and closures (FR-2.x)")
    samples = ['a,"b,c",d', 'a,"say ""hi""",d', 'a,,c,']
    for sample in samples:
        print("  parse", sample, "->", parse_raw_log_line(sample))
    audit_a = create_audit_filter(100)
    audit_b = create_audit_filter(500)
    print("FR-2.2 audit_a results:", [audit_a(x) for x in (50, 100, 150)],
          "| count a =", audit_a.audited_count(), "| count b =", audit_b.audited_count())
    audit_b(600)
    print("  after audit_b(600): count a =", audit_a.audited_count(), "| count b =", audit_b.audited_count())
    data = [("Acc1", "SAVINGS", 500), ("Acc2", "CURRENT", 700), ("Acc3", "SAVINGS", 900)]
    good = build_positional_filters(3)
    bad = build_positional_filters_buggy(3)
    print("FR-2.3 lambda k=k    : position 1 == SAVINGS ->", good[1](data, "SAVINGS"))
    print("       lambda NO k=k : position 0 == Acc1 (bug: looks at position 2) ->", bad[0](data, "Acc1"))


def demo_module_3():
    """Demonstrate FR-3.1 and FR-3.2."""
    banner("MODULE 3 - Inversion and in-place queue (FR-3.x)")
    raw_db = {
        "BRANCH_01": [("Acc101", {"DEPOSIT", "UPI"}), ("Acc102", {"LOAN", "UPI"})],
        "BRANCH_02": [("Acc101", {"SAVINGS", "UPI"}), ("Acc103", {"CARD", "DEPOSIT"})],
    }
    index = invert_services(raw_db)
    for tag in sorted(index):
        print("  ", tag, "->", index[tag])
    expected = [("Acc101", "BRANCH_01"), ("Acc101", "BRANCH_02"), ("Acc102", "BRANCH_01")]
    print("  UPI matches acceptance criterion:", index["UPI"] == expected)
    queue = [(5, 3, 9, 3), [4, 1, 3], {1, 2, 3, 4, 5, 6}, 7, 7, 8, 7, "x", "x"]
    id_before = id(queue)
    print("  before:", queue)
    clean_transaction_queue(queue)
    print("  after :", queue)
    print("  same list object (id unchanged):", id(queue) == id_before)


def seed_demo_database():
    """Create a sample accounts.db (the ONLY place a file is written with mode 'w';
    it just creates the starting file - all real updates use r+)."""
    with open(DB_FILE, "w", encoding="utf-8", newline="") as f:
        f.write("Acc101,SAVINGS,5200.00\n"
                "Acc102,CURRENT,-150.00\n"
                "THIS LINE IS BROKEN\n"
                "Acc103,CREDIT,20000.00\n"
                "Acc104,SAVINGS,abc\n"
                "Acc105,SAVINGS,3000.00\n"
                "Acc106,GOLD,10.00\n"
                "Acc107,CURRENT,750.50\n")


def read_lines(path):
    """Read a file as a list of lines (used only to compare before / after)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.readlines()


def demo_module_4():
    """Demonstrate FR-4.1, FR-4.2, FR-4.3."""
    banner("MODULE 4 - Files and exceptions (FR-4.x)")
    print("FR-4.1 hierarchy:", issubclass(CorruptedRecordError, BaseSystemError),
          issubclass(OutOfBoundsError, BaseSystemError), issubclass(InsufficientBalanceError, BaseSystemError))
    for error_class in (CorruptedRecordError, OutOfBoundsError, InsufficientBalanceError):
        try:
            raise error_class("demo")
        except BaseSystemError as err:
            print("  caught", type(err).__name__, "using the base class")
    seed_demo_database()
    before = read_lines(DB_FILE)
    print("accounts.db BEFORE:")
    for text in before:
        print("   ", text.rstrip("\n"))
    updates = {
        "Acc101": 123456789.5,     # longer record  -> tail shifts RIGHT
        "Acc102": 5,               # shorter record -> tail shifts LEFT + truncate
        "Acc103": 21000,           # same length    -> plain overwrite
        "Acc107": -20,             # accepted (CURRENT may be negative)
        "Acc105": -10,             # REJECTED (SAVINGS cannot be negative)
        "Acc999": 1,               # REJECTED (not in file)
    }
    counts = process_account_updates(DB_FILE, updates, chunk_size=8)    # tiny chunks on purpose
    after = read_lines(DB_FILE)
    print("accounts.db AFTER:")
    for text in after:
        print("   ", text.rstrip("\n"))
    untouched_ok = (len(before) == len(after))
    for position in range(len(before)):
        first_field = parse_raw_log_line(before[position].rstrip("\n"))[0]
        if first_field not in ("Acc101", "Acc102", "Acc103", "Acc107") and before[position] != after[position]:
            untouched_ok = False
    print("Neighbouring records byte-identical:", untouched_ok, "| counts:", counts)
    print("ledger.txt     :", len(read_lines(LEDGER_FILE)), "total entries (append-only)")
    print("corrupted.log  :", len(read_lines(CORRUPTED_LOG)), "total entries (append-only)")


def demo_module_5():
    """Demonstrate FR-5.1 and FR-5.2 / FR-5.3."""
    banner("MODULE 5 - OOP and polymorphism (FR-5.x)")
    savings = SavingsAccount("S-1", 5000)
    current = CurrentAccount("C-1", 200, overdraft_limit=1000)
    credit = CreditAccount("R-1", 10000)
    print("FR-5.1.1 total_accounts class attribute:", Account.total_accounts)
    print("FR-5.1.2 getters:", savings.get_account_id(), savings.get_balance())
    try:
        savings.set_balance("lots")
    except TypeError as err:
        print("  setter rejected bad input ->", err)
    print("FR-5.1.3 name mangling: savings._Account__balance =", savings._Account__balance)
    try:
        print(savings.__balance)         # outside the class: NOT mangled -> AttributeError
    except AttributeError as err:
        print("  savings.__balance fails ->", err)
    print("FR-5.2 individual rules:")
    for account, amount in ((savings, 4500), (current, 1100), (credit, 8000)):
        try:
            print("  ", type(account).__name__, "settle", amount, "->", account.process_settlement(amount))
        except BaseSystemError as err:
            print("  ", type(account).__name__, "settle", amount, "-> rejected:", type(err).__name__, err)
    print("FR-5.3 isolated batch (fresh accounts, amount 900):")
    mixed = [SavingsAccount("S-2", 1500), CurrentAccount("C-2", 100, 500), CreditAccount("R-2", 1000),
             SavingsAccount("S-3", 5000), Account("BASE-1", 100)]
    execute_batch_settlement(mixed, 900)


def main():
    """Run all demonstrations, then offer the interactive command loop."""
    demo_module_1()
    demo_module_2()
    demo_module_3()
    demo_module_4()
    demo_module_5()
    banner("INTERACTIVE MODE")
    try:
        answer = input("Start the interactive CLI now? (y/n): ").strip().lower()
    except EOFError:
        answer = "n"
    if answer == "y":
        print(HELP_TEXT)
        run_cli()


if __name__ == "__main__":
    main()
