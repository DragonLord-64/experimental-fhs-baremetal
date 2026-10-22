# manage_fhs_exporter

Deploy the Prometheus Exporter

## Variables

|     Variable Name    |                                                           Use                                                          |                       Example                      |
|:--------------------:|:----------------------------------------------------------------------------------------------------------------------:|:--------------------------------------------------:|
| **file_directory**   | File directory that contains the exporter tarball and service file.                                                    | "files"                                            |
| **exporter_file**    | Defines the tarball to install the Prometheus Exporter from.                                                           | "ska_mid_cbf_fhs_prometheus_exporter-0.0.2.tar.gz" |
| **exporter_service** | The service definition file that will be used by the hosts to spin up the Prometheus Exporter as a background service. | "prometheus-exporter.service"                      |
| **mft_version**      | The hosted version of MFT to install.                                                                                  | "4.20.0"                                           |

## Tags/Usage

### exporter_install
Installs the required libraries and tools for the exporter, then installs the exporter itself in the fhs venv. After this, installs the service file and uses it to run the exporter within the venv as a background service.

### exporter_restart
Restarts the exporter service.

### exporter_stop
Stops t he exporter service.