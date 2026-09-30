"""Four-file exact-source assembly on the dedicated N48X branch only.
The readable patch instruments existing API entry points; no context, storage, PG or
frozen candidate content is uploaded/retried here. Writes actual committed sources.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess
BASE = '0e3c12390ee0f7c2bd8ee9881b6630f4346038fd'
PAIRS = {'src/qbrain/ai/chat.cpp': ['0d3ae9fdaec9d9d0220c5ff34069878f6cdd9849', 'e8b0e4e5fa29569e5377ccec51c867c9d05008b4'], 'src/qbrain/ai/embed.cpp': ['b05f3adba1f2548d30ff06b2a2cfe6a9be3826c5', '310fbfa81331204a104083740f65af0ae2a97116'], 'src/qbrain/search/rerank.cpp': ['1e3eb613f7e12616d92f4ba764542534a67553be', '3e1b8b6b006e1b410cd82733ea918dbd5e45bfc9'], 'src/qbrain/main.cpp': ['2de65e27557b088127d22c15130fd7ef0df302a3', 'eeed13ab25894fdf5c99338f9045c09de921ca53']}
PATCH = r"""diff --git a/src/qbrain/ai/chat.cpp b/src/qbrain/ai/chat.cpp
index 0d3ae9f..e8b0e4e 100644
--- a/src/qbrain/ai/chat.cpp
+++ b/src/qbrain/ai/chat.cpp
@@ -1,2 +1,3 @@
 #include "qbrain/ai/chat.hpp"
+#include "qbrain/accounting/logical_observation.hpp"
 #include "qbrain/ai/http_client.hpp"
@@ -14,2 +15,3 @@ ChatResult chat_complete(const Config& cfg, const std::vector<ChatMessage>& mess
                          double temperature, int timeout_ms) {
+  return accounting::logical::invoke(accounting::logical::Kind::chat, [&](auto& observation) {
   ChatResult r;
@@ -17,2 +19,3 @@ ChatResult chat_complete(const Config& cfg, const std::vector<ChatMessage>& mess
   if (key.empty()) {
+    observation.path(accounting::logical::Path::missing_credentials);
     r.error = "missing chat API key";
@@ -21,2 +24,3 @@ ChatResult chat_complete(const Config& cfg, const std::vector<ChatMessage>& mess
   }
+  observation.path(accounting::logical::Path::remote_candidate);
   const bool use_responses =
@@ -110,2 +114,3 @@ ChatResult chat_complete(const Config& cfg, const std::vector<ChatMessage>& mess
   return r;
+  });
 }
diff --git a/src/qbrain/ai/embed.cpp b/src/qbrain/ai/embed.cpp
index b05f3ad..310fbfa 100644
--- a/src/qbrain/ai/embed.cpp
+++ b/src/qbrain/ai/embed.cpp
@@ -1,2 +1,3 @@
 #include "qbrain/ai/embed.hpp"
+#include "qbrain/accounting/logical_observation.hpp"
 #include "qbrain/ai/detail/embedding_response.hpp"
@@ -128,2 +129,3 @@ std::vector<float> mock_image_vector(std::string_view bytes) {
 EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts) {
+  return accounting::logical::invoke(accounting::logical::Kind::text_embedding, [&](auto& observation) {
   EmbedResult r;
@@ -131,2 +133,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
   if (texts.empty()) {
+    observation.path(accounting::logical::Path::empty_input);
     r.ok = true;
@@ -137,2 +140,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
       static_cast<std::size_t>(cfg.embedding_dimensions) > EMBED_MAX_DIMENSIONS) {
+    observation.path(accounting::logical::Path::invalid_input);
     r.error = "invalid embedding request";
@@ -141,2 +145,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
   if (embedding_mock_enabled()) {
+    observation.path(accounting::logical::Path::mock);
     r.ok = true;
@@ -152,2 +157,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
   if (key.empty()) {
+    observation.path(accounting::logical::Path::missing_credentials);
     r.error = "missing embedding API key";
@@ -155,2 +161,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
   }
+  observation.path(accounting::logical::Path::remote_candidate);
   json body;
@@ -172,2 +179,3 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
                                            cfg.embedding_dimensions);
+  });
 }
@@ -175,2 +183,4 @@ EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts
 ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
+  return accounting::logical::invoke(accounting::logical::Kind::image_embedding, [&](auto& observation) {
+  observation.path(accounting::logical::Path::invalid_input);
   ImageEmbedResult r;
@@ -178,2 +188,3 @@ ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
   auto degrade = [&](const std::string& message, bool no_credentials) {
+    observation.fallback(true);
     r.unavailable = true;
@@ -189,2 +200,3 @@ ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
   if (embedding_mock_enabled()) {
+    observation.path(accounting::logical::Path::mock);
     r.ok = true;
@@ -196,3 +208,7 @@ ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
   const std::string key = resolve_api_key(cfg, false);
-  if (key.empty()) return degrade("no provider credentials", true);
+  if (key.empty()) {
+    observation.path(accounting::logical::Path::missing_credentials);
+    return degrade("no provider credentials", true);
+  }
+  observation.path(accounting::logical::Path::remote_candidate);
   // Local magic sniff only to label the data URL; no image_meta dependency.
@@ -227,2 +243,3 @@ ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
   return r;
+  });
 }
diff --git a/src/qbrain/main.cpp b/src/qbrain/main.cpp
index 2de65e2..eeed13a 100644
--- a/src/qbrain/main.cpp
+++ b/src/qbrain/main.cpp
@@ -5,2 +5,3 @@
 #include "qbrain/accounting/observation_command.hpp"
+#include "qbrain/accounting/logical_command.hpp"
 #include "qbrain/accounting/cost_comparison.hpp"
@@ -14,2 +15,4 @@ namespace {
 int dispatch(int argc,char** argv) {
+  if(argc>1 && std::string(argv[1])=="observe-model")
+    return qbrain::accounting::logical::command(argc,argv,dispatch);
   if(argc>1 && std::string(argv[1])=="observe")
diff --git a/src/qbrain/search/rerank.cpp b/src/qbrain/search/rerank.cpp
index 1e3eb61..3e1b8b6 100644
--- a/src/qbrain/search/rerank.cpp
+++ b/src/qbrain/search/rerank.cpp
@@ -1,2 +1,3 @@
 #include "qbrain/search/rerank.hpp"
+#include "qbrain/accounting/logical_observation.hpp"
 #include "qbrain/util/utf8_display.hpp"
@@ -313,5 +314,9 @@ LlmAttempt reorder_from_content(const std::string& content,
 LlmAttempt request_native_rerank(const Config& cfg, const std::string& query,
-                                 const std::vector<SearchHit>& baseline, int timeout_ms) {
+                                 const std::vector<SearchHit>& baseline, int timeout_ms,
+                                 accounting::logical::Call& observation) {
   auto key = resolve_api_key(cfg, true);
-  if (key.empty()) return {false, {}, FailureReason::transport_error};
+  if (key.empty()) {
+    observation.path(accounting::logical::Path::missing_credentials);
+    return {false, {}, FailureReason::transport_error};
+  }
 
@@ -411,3 +416,8 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
                                       const RerankerOpts& opts) {
-  if (!opts.enabled || results.empty() || opts.top_n_in <= 0) return results;
+  return accounting::logical::invoke(accounting::logical::Kind::rerank, [&](auto& observation) {
+  if (!opts.enabled || results.empty() || opts.top_n_in <= 0) {
+    observation.path(results.empty()?accounting::logical::Path::empty_input:accounting::logical::Path::disabled);
+    return results;
+  }
+  observation.path(accounting::logical::Path::local_baseline);
 
@@ -430,6 +440,9 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
         if (opts.llm_fn_for_test) {
+          observation.path(accounting::logical::Path::callback);
           attempt = reorder_from_callback(opts.llm_fn_for_test(query, head), head);
         } else if (opts.llm_response_for_test) {
+          observation.path(accounting::logical::Path::callback);
           attempt = reorder_from_content(opts.llm_response_for_test(query, head), head);
         } else {
+          observation.path(accounting::logical::Path::remote_candidate);
           const int timeout_ms = opts.timeout_ms > 0
@@ -438,3 +451,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
           if (cfg.rerank_api_type == "native")
-            attempt = request_native_rerank(effective, query, head, timeout_ms);
+            attempt = request_native_rerank(effective, query, head, timeout_ms, observation);
           else
@@ -446,2 +459,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
 
+      observation.fallback(!attempt.ok);
       if (!attempt.ok) {
@@ -454,2 +468,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
     if (baseline.empty()) {
+      observation.fallback(true);
       auto fallback = original;
@@ -461,2 +476,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
     if (baseline.size() != original.size()) {
+      observation.fallback(true);
       auto fallback = original;
@@ -471,2 +487,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
   } catch (...) {
+    observation.fallback(true);
     auto fallback = original;
@@ -477,2 +494,3 @@ std::vector<SearchHit> apply_reranker(const Config& cfg, const std::string& quer
   }
+  });
 }
"""

def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def main(output):
    output.mkdir(parents=True,exist_ok=False)
    current={f:subprocess.check_output(['git','show','HEAD:'+f]) for f in PAIRS}
    for f,(old,new) in PAIRS.items():
        original=subprocess.check_output(['git','show',BASE+':'+f])
        if blob(original)!=old or Path(f).read_bytes()!=current[f]:raise ValueError('base/current bytes mismatch')
    before=all(blob(current[f])==PAIRS[f][0] for f in PAIRS)
    after=all(blob(current[f])==PAIRS[f][1] for f in PAIRS)
    if not before and not after:raise ValueError('refuse mixed or unrelated source state')
    (output/'runtime.patch').write_bytes(PATCH.encode())
    if before:
        subprocess.run(['git','apply','--check','--index',str((output/'runtime.patch').resolve())],check=True)
        subprocess.run(['git','apply','--index',str((output/'runtime.patch').resolve())],check=True)
    for f,(_,expected) in PAIRS.items():
        if blob(Path(f).read_bytes())!=expected:raise ValueError('assembled source mismatch')
    (output/'source-files.json').write_text(json.dumps(PAIRS,indent=2),encoding='utf8')
    print(json.dumps(dict(base=BASE,files=PAIRS,already_assembled=after)))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
