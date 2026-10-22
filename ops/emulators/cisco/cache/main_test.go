package main
import (
 "context"
 "net/http"
 "net/http/httptest"
 "sync"
 "sync/atomic"
 "testing"
 "time"
)
func TestFanoutFreshnessAndRecovery(t *testing.T) {
 var calls atomic.Int32
 var failed atomic.Bool
 body:="sts_psu1_fan{source=\"PSU1\"} 0\n"
 upstream:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
  calls.Add(1)
  if failed.Load(){http.Error(w,"failed",500);return};_,_=w.Write([]byte(body))
 }));defer upstream.Close()
 s:= &snapshot{ttl:time.Minute}
 check:=func(code int,want string){t.Helper();r:=httptest.NewRecorder();s.ServeHTTP(r,httptest.NewRequest("GET","/metrics",nil));if r.Code!=code || (code==200 && r.Body.String()!=want){t.Errorf("status/body: %d %q",r.Code,r.Body.String())}}
 check(503,"")
 if err:=s.collect(context.Background(),upstream.Client(),upstream.URL);err!=nil{t.Fatal(err)}
 var wg sync.WaitGroup
 for i:=0;i<128;i++{wg.Add(1);go func(){defer wg.Done();check(200,body)}()};wg.Wait()
 if calls.Load()!=1{t.Fatalf("fanout collected %d times",calls.Load())}
 fault:= &snapshot{ttl:time.Minute,body:[]byte("sts_psu1_fan{source=\"PSU1\"} 1\n"),collected:time.Now()}
 check(200,body)
 r:=httptest.NewRecorder();fault.ServeHTTP(r,httptest.NewRequest("GET","/metrics",nil));if r.Body.String()==body{t.Fatal("profiles mixed")}
 failed.Store(true)
 if s.collect(context.Background(),upstream.Client(),upstream.URL)==nil{t.Fatal("expected upstream failure")}
 check(200,body) // bounded last-known response, never refresh timestamp on failure
 s.mu.Lock();s.collected=time.Now().Add(-2*time.Minute);s.mu.Unlock()
 check(503,"")
 ready:=httptest.NewRecorder();s.ServeHTTP(ready,httptest.NewRequest("GET","/ready",nil));if ready.Code!=503{t.Fatal("expired readiness bypass")}
 failed.Store(false)
 if err:=s.collect(context.Background(),upstream.Client(),upstream.URL);err!=nil{t.Fatal(err)}
 check(200,body)
}
