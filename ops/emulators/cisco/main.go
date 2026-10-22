// Synthetic NX-OS monitoring subset. Wire types are Cisco's official protobufs.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	dialout "github.com/cisco-ie/nx-telemetry-proto/mdt_dialout"
	telemetry "github.com/cisco-ie/nx-telemetry-proto/telemetry_bis"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/proto"
)

type device struct {
	Name         string `json:"name"`
	Unit         string `json:"unit"`
	Role         string `json:"role"`
	ManagementIP string `json:"management_ip"`
	ChassisMAC   string `json:"chassis_mac"`
}
type link struct {
	LocalPort  string `json:"local_port"`
	RemotePort string `json:"remote_port"`
	State      string `json:"state"`
	Kind       string `json:"kind"`
	Neighbor   device `json:"neighbor"`
}
type switchDevice struct {
	device
	Links []link `json:"links"`
}
type topology struct {
	Synthetic bool           `json:"synthetic"`
	Switches  []switchDevice `json:"switches"`
}

func str(name, value string) *telemetry.TelemetryField {
	return &telemetry.TelemetryField{Name: name, ValueByType: &telemetry.TelemetryField_StringValue{StringValue: value}}
}
func uintf(name string, value uint64) *telemetry.TelemetryField {
	return &telemetry.TelemetryField{Name: name, ValueByType: &telemetry.TelemetryField_Uint64Value{Uint64Value: value}}
}
func group(name string, fields ...*telemetry.TelemetryField) *telemetry.TelemetryField {
	return &telemetry.TelemetryField{Name: name, Fields: fields}
}

// A DME subtree uses children/class/attributes; Telegraf promotes each dn to
// a tag before grouping. Flat attribute rows merge distinct interfaces.
func row(class string, attrs ...*telemetry.TelemetryField) *telemetry.TelemetryField {
	return group("", group("content", group("", group("children", group("", group(class, group("", group("attributes", group("", attrs...)))))))))
}
func message(sw switchDevice, path string, rows []*telemetry.TelemetryField, tick uint64) *telemetry.Telemetry {
	now := uint64(time.Now().UnixMilli())
	return &telemetry.Telemetry{NodeId: &telemetry.Telemetry_NodeIdStr{NodeIdStr: sw.Name}, Subscription: &telemetry.Telemetry_SubscriptionIdStr{SubscriptionIdStr: "lab-100"}, EncodingPath: path, CollectionId: tick, MsgTimestamp: now, DataGpbkv: rows}
}
func messages(sw switchDevice, tick uint64) []*telemetry.Telemetry {
	var interfaces, neighbors []*telemetry.TelemetryField
	for i, l := range sw.Links {
		dn := "sys/intf/phys-[" + l.LocalPort + "]/phys"
		interfaces = append(interfaces, row("ethpmPhysIf", str("dn", dn), str("operSt", l.State), str("operSpeed", "100G"), str("operDescr", l.Neighbor.Name+":"+l.RemotePort), uintf("operMtu", 9216), uintf("vdcId", 1)))
		// Official RMON HC class/path. Counters reset only with this process.
		for _, direction := range []string{"In", "Out"} {
			count := uint64(1000000) + uint64(i)*100
			packets := uint64(10000)
			if l.State == "up" {
				count += tick * 10000
				packets += tick * 100
			}
			interfaces = append(interfaces, row("rmonIfHC"+direction, str("dn", "sys/intf/phys-["+l.LocalPort+"]/dbgIfHC"+direction), uintf("octets", count), uintf("ucastPkts", packets)))
		}
		// LLDP is a static last-known neighbor inventory, including the failed link.
		capability := "station"
		if l.Kind == "mesh" {
			capability = "bridge,router"
		}
		neighbors = append(neighbors, row("lldpAdjEp", str("dn", "sys/lldp/inst/if-["+l.LocalPort+"]/adj-1"), uintf("id", 1), str("sysName", l.Neighbor.Name), str("portIdT", "if-name"), str("portIdV", l.RemotePort), str("portDesc", l.RemotePort), str("chassisIdT", "mac"), str("chassisIdV", l.Neighbor.ChassisMAC), str("mgmtIp", l.Neighbor.ManagementIP), str("capability", capability), str("enCap", capability)))
	}
	return []*telemetry.Telemetry{
		message(sw, "sys/intf", interfaces, tick), message(sw, "sys/lldp", neighbors, tick),
		message(sw, "sys/bd", []*telemetry.TelemetryField{row("l2VlanStats", str("dn", "sys/bd/bd-[vlan-501]/dbgVlanStats"), uintf("inUcastOctets", 1000000+tick*10000), uintf("outUcastOctets", 1000000+tick*10000))}, tick),
		message(sw, "sys/ch", []*telemetry.TelemetryField{row("eqptCh", str("dn", "sys/ch"), str("operSt", "online"), uintf("id", 1))}, tick),
	}
}
func run(ctx context.Context, t topology, target string, interval time.Duration, tick *uint64) error {
	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()
	stream, err := dialout.NewGRPCMdtDialoutClient(conn).MdtDialout(ctx)
	if err != nil {
		return err
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		for _, sw := range t.Switches {
			for _, m := range messages(sw, *tick) {
				data, err := proto.Marshal(m)
				if err != nil {
					return err
				}
				if err = stream.Send(&dialout.MdtDialoutArgs{ReqId: int64(*tick), Data: data}); err != nil {
					return err
				}
			}
		}
		log.Printf("sent collection %d (%d switches)", *tick, len(t.Switches))
		*tick = *tick + 1
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}
func main() {
	fixture := flag.String("topology", "/fixtures/topology.json", "synthetic topology JSON")
	target := flag.String("target", "switch-telegraf.fhs-platform.svc.cluster.local:57000", "isolated Telegraf gRPC endpoint")
	interval := flag.Duration("interval", 10*time.Second, "send interval")
	flag.Parse()
	if *interval <= 0 {
		log.Fatal("interval must be positive")
	}
	data, err := os.ReadFile(*fixture)
	if err != nil {
		log.Fatal(err)
	}
	var t topology
	if err = json.Unmarshal(data, &t); err != nil {
		log.Fatal(err)
	}
	if !t.Synthetic || len(t.Switches) == 0 {
		log.Fatal("nonempty synthetic topology required")
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	tick := uint64(0)
	for ctx.Err() == nil {
		if err := run(ctx, t, *target, *interval, &tick); err != nil {
			fmt.Fprintf(os.Stderr, "telemetry reconnect: %v\n", err)
		}
		select {
		case <-ctx.Done():
		case <-time.After(3 * time.Second):
		}
	}
}
