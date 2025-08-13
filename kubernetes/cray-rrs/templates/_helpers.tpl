{{/*
Generate list of critical service names as an array
*/}}
{{- define "cray-rrs.criticalServiceNamesList" -}}
{{- keys .Values.criticalServices | toYaml -}}
{{- end -}}
