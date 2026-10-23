{{/* Shared by the umbrella and child charts through Helm's global template table. */}}
{{- define "fhs-platform.prefix" -}}
{{- trimSuffix "/" .Values.global.urlPrefix -}}
{{- end -}}
{{- define "fhs-platform.origin" -}}
{{- printf "%s://%s" .Values.global.scheme .Values.global.hostname -}}
{{- end -}}
{{- define "fhs-platform.cookie" -}}
{{- printf "fhs_%s" (printf "%s/%s/%s" .Release.Namespace .Release.Name (include "fhs-platform.prefix" .) | sha256sum | trunc 12) -}}
{{- end -}}
