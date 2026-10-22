package main

import (
	"encoding/json"
	telemetry "github.com/cisco-ie/nx-telemetry-proto/telemetry_bis"
	"google.golang.org/protobuf/proto"
	"os"
	"testing"
)

func findAttributes(f *telemetry.TelemetryField) []*telemetry.TelemetryField {
	if f.Name == "attributes" {
		return f.Fields[0].Fields
	}
	for _, child := range f.Fields {
		if found := findAttributes(child); found != nil {
			return found
		}
	}
	return nil
}
func TestWireContract(t *testing.T) {
	raw, err := os.ReadFile("../fixtures/topology.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture topology
	if err = json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	for _, sw := range fixture.Switches {
		all := messages(sw, 3)
		if len(all) != 4 {
			t.Fatal("expected interface,LLDP,VLAN,chassis")
		}
		for _, m := range all {
			raw, err := proto.Marshal(m)
			if err != nil {
				t.Fatal(err)
			}
			var decoded telemetry.Telemetry
			if err = proto.Unmarshal(raw, &decoded); err != nil {
				t.Fatal(err)
			}
			if decoded.GetNodeIdStr() != sw.Name || decoded.MsgTimestamp == 0 {
				t.Fatal("source/timestamp absent")
			}
		}
		if len(all[1].DataGpbkv) != len(sw.Links) {
			t.Fatal("wrong neighbor count")
		}
		for i, r := range all[1].DataGpbkv {
			attrs := map[string]*telemetry.TelemetryField{}
			for _, a := range findAttributes(r) {
				attrs[a.Name] = a
			}
			l := sw.Links[i]
			if attrs["sysName"].GetStringValue() != l.Neighbor.Name || attrs["portIdV"].GetStringValue() != l.RemotePort {
				t.Fatal("wrong neighbor")
			}
			if attrs["dn"].GetStringValue() != "sys/lldp/inst/if-["+l.LocalPort+"]/adj-1" {
				t.Fatal("wrong localport")
			}
			if attrs["id"].GetUint64Value() != 1 {
				t.Fatal("neighbor id must remain gauge1")
			}
		}
	}
}
