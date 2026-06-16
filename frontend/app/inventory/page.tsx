import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { DataTable } from "@/components/DataTable";

export default async function InventoryPage() {
  const rows: any[] = await apiGet("/api/inventory");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Инвентаризация</h2>
        <p className="text-gray-500">Снимки состояния удалённых узлов</p>
      </div>
      <div className="panel">
        <DataTable
          columns={[
            { title: "ID", key: "id" },
            { title: "Host ID", key: "host_id" },
            { title: "Hostname", key: "hostname" },
            { title: "OS", key: "os_name" },
            { title: "Kernel", key: "kernel" },
            { title: "RAM MB", key: "ram_mb" },
            { title: "Disk free GB", key: "disks_free_gb" },
            { title: "Дата", render: (r) => formatDate(r.collected_at) },
          ]}
          rows={rows || []}
        />
      </div>
    </div>
  );
}
