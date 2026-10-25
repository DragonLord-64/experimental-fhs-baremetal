{{- define "fhs-platform.discovery" -}}
{{- range $job := list (dict "name" "node-netbox" "legacy" "node" "tag" .Values.global.discovery.nodeTag "choice" "node" "port" 9100) (dict "name" "fhs-netbox" "legacy" "fhs-exporter" "tag" .Values.global.discovery.fhsTag "choice" "fhs" "port" 9110) }}
{{- $filter := printf "tag=%s" ($job.tag | urlquery) }}
{{- if eq $.Values.global.discovery.selector "customField" }}
{{- $filter = printf "cf_%s=%s" $.Values.global.discovery.customField $job.choice }}
{{- end }}
- job_name: {{ $job.name }}
  http_sd_configs:
  - url: {{ printf "http://fhs-netbox.%s.svc%s/netbox/api/plugins/prometheus-sd/devices/?status=active&%s" $.Release.Namespace (include "fhs-platform.prefix" $) $filter | quote }}
    refresh_interval: {{ $.Values.global.discovery.refreshInterval }}
    authorization:
      type: Token
      credentials_file: {{ printf "/etc/netbox-discovery/%s" $.Values.global.discovery.secretKey | quote }}
  relabel_configs:
  - target_label: job
    replacement: {{ $job.legacy }}
  - source_labels: [__meta_netbox_status]
    regex: active
    action: keep
  - source_labels: [__meta_netbox_primary_ip4]
    regex: .+
    action: keep
  - source_labels: [__meta_netbox_primary_ip4]
    target_label: __address__
    replacement: {{ printf "${1}:%d" $job.port | quote }}
  - source_labels: [__meta_netbox_name]
    target_label: node_name
  - source_labels: [__meta_netbox_name]
    target_label: device
  - source_labels: [__meta_netbox_site_slug]
    target_label: site
  - source_labels: [__meta_netbox_role_slug]
    target_label: role
  - target_label: __metrics_path__
    replacement: /metrics
  - target_label: __scheme__
    replacement: http
{{- end }}
{{- end -}}
