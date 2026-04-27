---
title: "实验室服务器跨平台存储挂载配置"
tags:
  - technical-docs
  - server-management
  - samba
---

## 1. 背景与环境拓扑

为了将实验室服务器 (`jiagpu3`) 上的大容量存储数据及特定容器的数据卷，稳定地挂载到内网 Windows 工作站及其他 Linux 计算节点，以便于进行数据分析和可视化处理。

初期尝试使用 NFS 协议，但由于校内防火墙对高位端口的严格限制，以及 Windows 系统对 NFS 兼容性较差，最终弃用。现行生产环境全面采用 **Samba (SMB) 协议** 进行 Docker 容器化部署。

**环境拓扑信息**

| **角色**     | **主机名** | **IP 地址 (内网/公网)**                  | **操作系统**  | **备注**               |
| ------------ | ---------- | ---------------------------------------- | ------------- | ---------------------- |
| **服务端**   | jiagpu3    | `<server-lan-ip>` / `<server-public-ip>` | CentOS 7/8    | 运行 Docker Samba 容器 |
| **客户端 A** | Windows PC | 自动获取                                 | Windows 10/11 | 数据可视化与处理终端   |
| **客户端 B** | jiagpu2    | `<linux-client-lan-ip>`                  | CentOS 7/8    | Linux 数据处理节点     |

**核心共享数据路径：**

1. **公共数据池 (`all_data`)**: `/beegfs_hdd/data/nfs_share/share/micelab/all_data`
2. **高速分析数据 (`ssd_data`)**: 容器数据卷的底层物理路径（通过排查确认为 `/nvmessd/docker/volumes/mice_data/_data`）

---

## 2. 弃用方案留档：NFS 容器化部署记录

_(注：此方案仅适用于纯 Linux 内网互信环境，在涉及 Windows 及复杂防火墙策略时表现不佳，仅作技术留档)_

部署依赖于 `erichough/nfs-server` 镜像。若服务器拉取超时，可通过本地 VPN 环境使用 Docker Desktop 拉取后转移至服务器。

Bash

```
# 本地拉取并导出
docker pull erichough/nfs-server
docker save -o nfs-server.tar erichough/nfs-server

# 服务器端导入并运行
docker load -i nfs-server.tar
docker run -d \
  --name nfs-server \
  --privileged \
  --net=host \
  --restart=unless-stopped \
  -v /beegfs_hdd/data/nfs_share/share/micelab/all_data:/data \
  -e NFS_EXPORT_0='/data *(rw,sync,no_subtree_check,no_root_squash,insecure,fsid=0)' \
  erichough/nfs-server
```

**Linux 客户端挂载命令：**

Bash

```
sudo mkdir -p mydata
sudo mount -t nfs <server-lan-ip>:/ mydata
```

_Windows 失败原因：NFS 默认需要动态的高位端口进行 RPC 绑定，校网/内网防火墙通常会将其拦截。_

---

## 3. 生产环境部署：Samba (SMB) 多目录与权限对齐方案

Samba 方案的核心难点在于**跨系统与跨容器的权限一致性**。若直接以 Root 权限运行 Samba，Windows 写入的文件将导致 Linux 容器内（如 `mice` 容器中的 `user` 账户）的 Python 脚本遭遇 `Permission denied` 错误。因此，必须进行底层 UID/GID 对齐。

### 3.1 前置准备与物理路径确认

1. **端口与防火墙放行**：确认宿主机 445 端口未被占用，并永久放行 Samba 服务。

   Bash

   ```
   systemctl start firewalld
   firewall-cmd --permanent --add-service=samba
   firewall-cmd --reload
   ```

2. **确认 Docker 卷真实路径**：若要共享其他容器内的数据（如 `ssd_data`），切忌直接挂载容器内的软链接。需在宿主机使用 `docker inspect` 查找真实物理路径。

   Bash

   ```
   docker inspect --format='{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' mice
   # 输出示例: /nvmessd/docker/volumes/mice_data/_data -> /ssd_data
   ```

### 3.2 容器启动策略（原生 UID 映射）

为彻底解决权限壁垒，避免修改 `[global]` 配置文件导致的容器假死（`unhealthy` 状态），采用 `dperson/samba` 镜像并利用其原生的账号创建参数直接对齐 Linux 用户的 UID。

已知内部处理容器（如 `mice`）的运行用户 UID 和 GID 均为 `1000`。

Bash

```
docker run -it -d \
  --name samba \
  --restart=always \
  --net=host \
  -v /beegfs_hdd/data/nfs_share/share/micelab/all_data:/mount_all \
  -v /nvmessd/docker/volumes/mice_data/_data:/mount_ssd \
  docker.1ms.run/dperson/samba \
  -u "<smb-user>;<smb-password>;1000;1000" \
  -s "all_data;/mount_all;yes;no;yes;all;<smb-user>;all" \
  -s "ssd_data;/mount_ssd;yes;no;yes;all;<smb-user>;all" \
  -w "WORKGROUP" \
  -p
```

**关键参数解析：**

- `--net=host`: 直接使用宿主机网络栈，避免端口映射损失性能。
- `-v`: 映射多路物理路径到 Samba 容器内的虚拟路径。
- `-u "账号;密码;UID;GID"`: 核心权限配置。强制 Samba 在底层以 `UID 1000` 的身份创建共享账户。Windows 客户端的任何写入操作，底层属主皆为 `1000:1000`，与 Linux 处理节点完全互通。
- `-s`: 定义多个共享池规则。

### 3.3 移交历史文件所有权 (关键)

新部署的权限规则只对新文件生效。历史由 Root 创建的文件仍会阻碍访问，需在宿主机执行一次性的权限下放：

Bash

```
chown -R 1000:1000 /beegfs_hdd/data/nfs_share/share/micelab/all_data
chown -R 1000:1000 /nvmessd/docker/volumes/mice_data/_data
```

---

## 4. Windows 客户端挂载与故障排查指南

在服务器端部署完成后，Windows 10/11 客户端通过资源管理器地址栏输入 `\\<server-public-ip>` 或内网 IP 进行访问。右键目录可选择“映射网络驱动器”分配固定盘符。

若连接失败，请严格按照以下层级排查：

### 4.1 网络与服务端状态自检

1. **确认容器状态**：服务器执行 `docker ps -a | grep samba`。状态必须为 `Up (healthy)` 或 `Up (health: starting)`。若出现反复重启，检查 Docker 启动命令的路径是否有误。
2. **确认端口监听**：服务器执行 `ss -ntlp | grep 445`。若无输出，说明 445 端口未被绑定，可能存在僵尸进程，需执行 `killall smbd nmbd` 后重启容器。

### 4.2 Windows 凭据冲突与“找不到网络路径”（极高频故障）

**现象**：提示“指定的网络文件夹目前是以其他用户名和密码进行映射的”，或在清理凭据后提示“找不到网络路径”。

**原因**：Windows 底层的 `LanmanWorkstation`（工作站服务）存在顽固的网络状态缓存，协议特征变更时极易发生内部死锁，导致请求被静默丢弃。

**解决标准流程（请按顺序执行）：**

1. **强制切断缓存**：打开 CMD (管理员)，执行 `net use * /delete /y`。
2. **清理本地凭据**：控制面板 -> 凭据管理器 -> Windows 凭据，删除所有相关 IP 的历史记录。
3. **物理阻断（最有效）**：**直接重启 Windows 电脑。**（注：并非关机再开机，必须点击“重启”以清空内核网络状态机）。
4. **重新连接**：开机后，在地址栏直接输入 `\\<server-public-ip>`，触发全新的凭据握手，输入共享账号与密码。

### 4.3 跨系统并发写入的锁冲突 (SMB Oplocks)

**现象**：在容器内运行 Python 脚本进行文件操作（如 `os.rename` 或覆写）时，终端偶尔抛出 `PermissionError: [Errno 13] Permission denied`，但文件 `ls -l` 权限显示完美（皆为 `user:user`）。

**原因**：Windows 资源管理器在后台扫描共享文件夹（为了生成缩略图或安全扫描）时，会通过 Samba 对文件施加“只读共享锁 (Oplocks)”。此时 Linux 内核会拦截 Python 的瞬间修改请求。

**解决方案**：

- 运行高并发文件生成的 Python 脚本时，**暂时关闭 Windows 端所有指向该共享路径的文件夹窗口**。
- 确保 Python 脚本的工作目录（临时文件生成区）与最终结果的输出目录分离，减少 Windows 后台扫描的频次。
