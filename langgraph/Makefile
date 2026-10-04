# receipts/langgraph: LangGraph Functional API (@task + interrupt), durability="sync".
# spec/ is copied unmodified from untyped-ai/untyped (MIT). Do not edit it here.
CP  = tools/tla2tools.jar:tools/CommunityModules-deps.jar
TLC = java -XX:+UseSerialGC -cp $(CP) tlc2.TLC -config spec/harnessTrace.cfg -workers 1 -metadir states -nowarning spec/harnessTrace.tla

# Kill the process 50 ms after the task returns while the task's pending write is
# held for 200 ms, so the write is still in flight when the process dies.
repro: .venv
	WRITE_DELAY_MS=200 OUT=out ./driver.sh repro after_task:50 && $(MAKE) -s verdict TRACE=out/repro.jsonl

# Control: the same delay, but kill 500 ms after, once the write has landed.
control: .venv
	WRITE_DELAY_MS=200 OUT=out ./driver.sh control after_task:500 && $(MAKE) -s verdict TRACE=out/control.jsonl

# No delay. Whether the write lands before the process dies depends on the host.
natural: .venv
	OUT=out ./driver.sh natural after_task:0 && $(MAKE) -s verdict TRACE=out/natural.jsonl

# The natural race at 0, 1, 10, 100 and 1000 ms.
schedules: .venv
	for d in 0 1 10 100 1000; do OUT=out ./driver.sh kill$$d after_task:$$d; done

# Raw TLC output for one run: make check TRACE=out/repro.jsonl
check:
	TRACE=$(TRACE) $(TLC)

# accepted / violated / rejected for one run; full TLC output goes to $(TRACE).tlc.out
verdict:
	@TRACE=$(TRACE) $(TLC) >$(TRACE).raw 2>&1; rc=$$?; \
	sed -e 's#$(CURDIR)/##g' -e 's#[^ (]*/tlc-[0-9]*/#<tmp>/#g' $(TRACE).raw >$(TRACE).tlc.out; rm -f $(TRACE).raw; \
	case $$rc in 0) v=accepted;; 10) v=rejected;; 12) v=violated;; *) echo "$(TRACE): tlc exit=$$rc"; exit $$rc;; esac; \
	grep -E "^State [0-9]|^/\\\\ (effects|attempt)|^Error: (Invariant|Postcondition)|states generated" $(TRACE).tlc.out; \
	echo "$(TRACE): $$v (tlc exit=$$rc)"

.venv:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.lock.txt

.PHONY: repro control natural schedules check verdict
