// Cache actual native exporter bytes. No metrics are synthesized or relabeled.
package main

import (
 "context"
 "flag"
 "io"
 "log"
 "net/http"
 "sync"
 "time"
)

type snapshot struct {
 mu sync.RWMutex
 body []byte
 collected time.Time
 ttl time.Duration
}

func (s *snapshot) collect(ctx context.Context, client *http.Client, url string) error {
 req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
 if err != nil { return err }
 r, err := client.Do(req)
 if err != nil { return err }
 defer r.Body.Close()
 if r.StatusCode != http.StatusOK { return &upstreamError{} }
 b, err := io.ReadAll(io.LimitReader(r.Body, 4*1024*1024+1))
 if err != nil { return err }
 if len(b)==0 || len(b)>4*1024*1024 { return &upstreamError{} }
 s.mu.Lock()
 s.body=b; s.collected=time.Now()
 s.mu.Unlock()
 return nil
}
type upstreamError struct{}
func (*upstreamError) Error() string { return "invalid upstream response" }
func (s *snapshot) ServeHTTP(w http.ResponseWriter, r *http.Request) {
 if r.URL.Path!="/metrics" && r.URL.Path!="/ready" { http.NotFound(w,r); return }
 s.mu.RLock()
 b, at := s.body,s.collected
 s.mu.RUnlock()
 if at.IsZero() || time.Since(at)>=s.ttl {
  http.Error(w,"native exporter snapshot unavailable or expired",http.StatusServiceUnavailable); return
 }
 w.Header().Set("Content-Type","text/plain; version=0.0.4")
 w.Header().Set("X-Exporter-Collected-At",at.UTC().Format(time.RFC3339Nano))
 if r.URL.Path=="/metrics" { _,_ = w.Write(b) }
}
func run(ctx context.Context,s *snapshot,url string,interval time.Duration) {
 client:= &http.Client{Timeout:4*time.Second}
 for {
  if err:=s.collect(ctx,client,url); err!=nil && ctx.Err()==nil { log.Print("native collection failed") }
  timer:=time.NewTimer(interval)
  select { case <-ctx.Done(): timer.Stop();return; case <-timer.C: }
 }
}
func main() {
 listen:=flag.String("listen",":9210","cache listener")
 upstream:=flag.String("upstream","http://127.0.0.1:9110/metrics","actual native exporter")
 flag.Parse()
 s:= &snapshot{ttl:15*time.Second}
 go run(context.Background(),s,*upstream,5*time.Second)
 log.Fatal((&http.Server{Addr:*listen,Handler:s,ReadHeaderTimeout:2*time.Second,WriteTimeout:5*time.Second}).ListenAndServe())
}
