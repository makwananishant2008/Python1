# PTMAE Documentation (D2)

Pure Python Transactional Micro-Banking & Audit Engine, PTMAE-SRS-1.0
Run with: `python main.py` (Python 3.x, only `datetime` imported)

## (a) ASCII class and architecture diagram

```
                           main.py  (single file)
 +---------------------------------------------------------------------+
 | SECTION 0  helpers: timestamp(), to_finite_number(), banner()       |
 +---------------------------------------------------------------------+
 | MODULE 1 (Unit 1)  State engine                                     |
 |   run_cli()  --(outer while / inner while)--> execute_command()     |
 |   compound_interest()  penalty_fee()  trajectory_guard()            |
 +----------------------------+----------------------------------------+
                              | uses (tokenize_command)
 +----------------------------v----------------------------------------+
 | MODULE 2 (Unit 2)  Parser + closures                                |
 |   parse_raw_log_line()   create_audit_filter() -> validate()        |
 |   build_positional_filters() -> [lambda k=k ...]                    |
 +----------------------------+----------------------------------------+
                              | used by validate_record()
 +----------------------------v----------------------------------------+
 | MODULE 3 (Unit 3)  invert_services()   clean_transaction_queue()   |
 +---------------------------------------------------------------------+
 | MODULE 4 (Unit 4)  Files + exceptions                               |
 |                                                                     |
 |   Exception                                                         |
 |     +-- BaseSystemError                                             |
 |           +-- CorruptedRecordError                                  |
 |           +-- OutOfBoundsError                                      |
 |           +-- InsufficientBalanceError                              |
 |                                                                     |
 |   process_account_updates() -> validate_record() / validate_update()|
 |        |-> rewrite_line_in_place()  (r+, tell, seek, truncate)      |
 |        |-> write_ledger()      --> ledger.txt     (append)          |
 |        '-> log_corrupted()     --> corrupted.log  (append)          |
 |   accounts.db  (read/write r+)                                      |
 +----------------------------+----------------------------------------+
                              | raises BaseSystemError subclasses
 +----------------------------v----------------------------------------+
 | MODULE 5 (Unit 5)  Polymorphic engine                               |
 |                                                                     |
 |   Account  (total_accounts, _account_id, __balance)                 |
 |     |  get/set_balance, get/set_account_id, _validate_amount()      |
 |     |  process_settlement()  <- overridden below                    |
 |     +-- SavingsAccount  (balance after settlement >= 1000)          |
 |     +-- CurrentAccount  (__overdraft_limit)                         |
 |     '-- CreditAccount   (amount * 1.025 against credit limit)       |
 |                                                                     |
 |   execute_batch_settlement(list, amount)                            |
 |        for each account: try / except  (fault isolation)           |
 +---------------------------------------------------------------------+
 | SECTION 6  demo_module_1() ... demo_module_5(), main()              |
 +---------------------------------------------------------------------+
```

## (b) State and scope tracking table

| Name | Where defined | Kind of scope | Who changes it | Notes |
|---|---|---|---|---|
| `PROMPT`, `TERMINATE_FLAG`, `VALID_TYPES`, `DB_FILE`, `LEDGER_FILE`, `CORRUPTED_LOG` | module top | global **constants** | nobody (read only) | Never used to pass state to closures. No `global` keyword exists in the program. |
| `count` | `create_audit_filter` | enclosing (nonlocal) | `validate()` via `nonlocal count` | Every call of `create_audit_filter` makes a separate `count`. |
| `validate`, `audited_count` | inside `create_audit_filter` | local to factory | returned to caller | `audited_count` only reads `count`. |
| `k` (lambda default) | `build_positional_filters` | lambda default argument | fixed when the lambda is created (`k=k`) | The buggy demo version looks `k` up at call time (late binding). |
| `data_list` | `clean_transaction_queue` parameter | local name, same object as caller's list | mutated by index assignment, `del`, `.sort()` | Never rebound, so `id(data_list)` stays the same. |
| `tokens`, `current`, `in_quotes`, `was_quoted`, `index` | `parse_raw_log_line` | local state flags | the parser loop | Hand-made state machine. |
| `counts`, `seen_ids`, `line_number` | `process_account_updates` | local | the scan loop | Reported in the `finally` block. |
| `Account.total_accounts` | class body | class attribute | `Account.__init__` | Shared by all accounts. |
| `self._account_id` | `Account.__init__` | protected (convention) | `set_account_id` | Visible to subclasses. |
| `self.__balance` | `Account.__init__` | private, mangled to `_Account__balance` | `set_balance` | `obj._Account__balance` works, `obj.__balance` raises `AttributeError`. |
| `self.__overdraft_limit` | `CurrentAccount.__init__` | private, mangled to `_CurrentAccount__overdraft_limit` | constructor only | Read via `get_overdraft_limit()`. |
| `self.__credit_limit` | `CreditAccount.__init__` | private, mangled to `_CreditAccount__credit_limit` | constructor only | Read via `get_credit_limit()`. |

## (c) Module compliance checklist (Units 1-5)

| Req | Where in `main.py` | Status |
|---|---|---|
| FR-1.1 nested `while` event loop, exits only on `exit` | `run_cli` | Done |
| FR-1.2 interest/penalty using `+ - * / // % **` in loops, no `math` | `compound_interest`, `penalty_fee` (`**` only in the demo check) | Done |
| FR-1.3 guard with short-circuit `or`, two halt conditions | `trajectory_guard` | Done |
| FR-2.1 / 2.1.1 manual index-by-index parser with slicing and flags | `parse_raw_log_line` | Done |
| FR-2.1.2 delimiter inside quotes is data | same | Done |
| FR-2.1.3 `""` becomes one `"` | same | Done |
| FR-2.1.4 empty fields and trailing delimiter | same | Done |
| FR-2.2 closure with `nonlocal` counter | `create_audit_filter` | Done |
| FR-2.3 lambdas in a loop with `k=k`, no globals | `build_positional_filters` | Done |
| FR-3.1 single dict comprehension reverse index | `invert_services` | Done |
| FR-3.2 in-place queue clean (4 operations) | `clean_transaction_queue` | Done |
| FR-4.1 exception hierarchy | `BaseSystemError` and 3 subclasses | Done |
| FR-4.2 `r+`, `tell`, `seek`, `truncate`, chunked shifting | `process_account_updates`, `rewrite_line_in_place` | Done |
| FR-4.3 try-except-else-finally, `corrupted.log`, `ledger.txt`, counts | `process_account_updates`, `log_corrupted`, `write_ledger` | Done |
| FR-5.1 encapsulation, name mangling, `super()` | `Account` and 3 subclasses | Done |
| FR-5.2 overridden `process_settlement` | three subclasses | Done |
| FR-5.3 isolated batch with report | `execute_batch_settlement` | Done |
| NFR-1..7 (no crash, isolation, `with`, portability, docstrings, demo, clear messages) | whole file | Done |
| Section 5.1 only `datetime` imported | line 9 | Done |
| Section 5.2 no shortcut methods in parser, no `max`/`min`/`sum` | whole file (checked by search) | Done |
| Section 5.3 no globals for state, no rebinding of `data_list` | whole file | Done |
| Section 5.4 no `"w"` rewrite for updates, every file in `with` | only `seed_demo_database` uses `"w"` to create the sample file | Done |

## Design notes

- **Record format:** `AccountID,TYPE,Balance` e.g. `Acc101,SAVINGS,5200.00`. A record is corrupted for a wrong field count, a non-numeric balance, an unknown type, or non-ASCII text.
- **ASCII rule:** records must be ASCII so that text-mode offsets from `tell()` equal character counts when shifting the file tail.
- **Deduplication in FR-3.2:** applies to the top-level primitive values (ints, floats, strings) of the queue.
- **Credit account:** `balance` means available credit. Each settlement costs `amount + 2.5%`, and exceeding the available credit raises `OutOfBoundsError`.
- **Rejected counts:** the report counts corrupted lines, rejected updates and update ids that were not found in the file.
