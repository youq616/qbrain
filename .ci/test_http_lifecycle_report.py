import unittest
from validate_http_lifecycle import validate_report, VARIANTS

SOURCE = "a" * 40
HASHES = {"legacy": "1" * 64, "per_call": "2" * 64, "current": "3" * 64}


def fixture():
    out = {"result":"PASS", "native_windows":True, "source_commit":SOURCE,
           "rounds_per_variant":8, "requests_per_round":32, "allowed_growth":16,
           "session_policy":"shared_immutable_request_timeouts", "variants":{}}
    for name in VARIANTS:
        rows=[]
        for n in range(1,9):
            shared=name.startswith("current")
            opened=n*(64 if shared else 96)+int(shared)
            rows.append(dict(cache_released=False,timeout_count=32, requested=32, opened=opened, closed=opened-int(shared),
                close_errors=0, states_created=n*32, states_destroyed=n*32, final_callbacks=n*32,
                callbacks_without_parents=n*32 if name=="legacy" else 0,
                handles_at_250ms=180+n, handles_at_2000ms=180+n))
        shutdown=dict(rows[-1],cache_released=True,timeout_count=0,requested=0,closed=rows[-1]["opened"])
        out["variants"][name]={"shutdown":shutdown,"sha256":HASHES["current" if name=="current_repeat" else name],
                              "samples":rows, "exit_code":0}
    return out


class LifecycleReportTests(unittest.TestCase):
    def validate(self, report):
        return validate_report(report, source_commit=SOURCE, probe_hashes=HASHES)

    def test_complete_schedule(self):
        self.assertEqual(self.validate(fixture())["current_requests"],512)

    def test_controls_are_not_current_acceptance(self):
        r=fixture()
        r["variants"]["legacy"]["samples"][-1]["handles_at_2000ms"]=999
        r["variants"]["per_call"]["samples"][-1]["handles_at_2000ms"]=999
        self.validate(r)

    def test_missing_and_extra_variants(self):
        for name in VARIANTS:
            r=fixture();del r["variants"][name]
            with self.subTest(name=name), self.assertRaises(ValueError): self.validate(r)
        r=fixture();r["variants"]["surprise"]={}
        with self.assertRaises(ValueError): self.validate(r)

    def test_empty_partial_or_extra_rows(self):
        for count in (0,1,7,9):
            r=fixture()
            r["variants"]["current"]["samples"]=(r["variants"]["current"]["samples"]*2)[:count]
            with self.subTest(count=count), self.assertRaises(ValueError): self.validate(r)

    def test_both_current_runs_must_pass(self):
        for name in ("current","current_repeat"):
            r=fixture();r["variants"][name]["samples"][-1]["handles_at_2000ms"]=198
            with self.subTest(name=name), self.assertRaises(ValueError): self.validate(r)

    def test_exact_original_ceiling(self):
        r=fixture();r["variants"]["current"]["samples"][-1]["handles_at_2000ms"]=197
        self.validate(r)
        r["allowed_growth"]=17
        with self.assertRaises(ValueError): self.validate(r)

    def test_owned_handles_state_callbacks_and_timeouts(self):
        for key in ("closed","opened","close_errors","states_created","states_destroyed",
                    "final_callbacks","callbacks_without_parents","requested","timeout_count"):
            r=fixture();r["variants"]["current"]["samples"][3][key]+=1
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(r)

    def test_bad_numeric_fields(self):
        for val in (None,True,-1,float("nan"),float("inf"),"181"):
            r=fixture();r["variants"]["current"]["samples"][0]["handles_at_2000ms"]=val
            with self.subTest(value=val), self.assertRaises(ValueError): self.validate(r)

    def test_wrong_binary_source_or_policy(self):
        for field,val in (("source_commit","b"*40),("native_windows",False),
                          ("session_policy","global"),("result","FAIL"),
                          ("requests_per_round",31),("rounds_per_variant",7)):
            r=fixture();r[field]=val
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(r)
        r=fixture();r["variants"]["current_repeat"]["sha256"]="4"*64
        with self.assertRaises(ValueError): self.validate(r)

    def test_failed_or_absent_exit_code(self):
        for val in (None,True,1,-1):
            r=fixture();r["variants"]["current"]["exit_code"]=val
            with self.subTest(value=val), self.assertRaises(ValueError): self.validate(r)

    def test_cannot_validate_incomplete_pending_report(self):
        r=fixture();r["result"]="FAIL";r["variants"]["per_call"]["samples"]=[]
        with self.assertRaises(ValueError):
            validate_report(r,source_commit=SOURCE,probe_hashes=HASHES,require_pass=False)

    def test_pending_evidence_checked_before_success(self):
        r=fixture();r["result"]="FAIL"
        self.assertEqual(validate_report(r,source_commit=SOURCE,probe_hashes=HASHES,
                                        require_pass=False)["variants"],4)


    def test_shutdown_is_required_and_balanced(self):
        for name in VARIANTS:
            r=fixture();del r["variants"][name]["shutdown"]
            with self.subTest(name=name), self.assertRaises(ValueError): self.validate(r)
        for key,value in (("cache_released",False),("closed",512),("timeout_count",1),("states_destroyed",255)):
            r=fixture();r["variants"]["current"]["shutdown"][key]=value
            with self.subTest(field=key), self.assertRaises(ValueError): self.validate(r)

    def test_cached_session_cannot_be_hidden_or_duplicated(self):
        for key,value in (("opened",96),("closed",65),("cache_released",True)):
            r=fixture();r["variants"]["current"]["samples"][0][key]=value
            with self.subTest(field=key), self.assertRaises(ValueError): self.validate(r)

if __name__ == "__main__":
    unittest.main(verbosity=2)
