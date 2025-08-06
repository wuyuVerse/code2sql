# Git网络连通性问题解决方案

## 问题描述
- 服务器（110.40.151.107）无法直接访问内网Git仓库（git.woa.com）
- 需要配置SSH密钥直接连接工蜂

## 解决方案：直接SSH密钥配置

### 步骤1：检查SSH密钥
```bash
cat ~/.ssh/id_rsa.pub
```
如果没有密钥，则生成：
```bash
ssh-keygen -t rsa
```

### 步骤2：配置SSH连接信息
编辑 `~/.ssh/config` 文件：
```bash
Host git.woa.com
Hostname git.woa.com
User git
Port 22
IdentityFile ~/.ssh/id_rsa
```

### 步骤3：添加公钥到工蜂
将 `~/.ssh/id_rsa.pub` 的内容复制到工蜂个人设置的SSH密钥页面

### 步骤4：配置Git仓库
```bash
git remote set-url origin git@git.woa.com:felixyuwu/code2sql.git
```

### 步骤5：测试连接
```bash
ssh -T git@git.woa.com
```

### 步骤6：推送代码
```bash
git push --set-upstream origin --all
```

## 当前配置状态
- SSH密钥已存在：`ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDrdxDCOcZ2McVPQhuL1QjveQhNWoN4G/wBisr36SHk...`
- SSH配置已更新
- Git仓库地址已配置为：`git@git.woa.com:felixyuwu/code2sql.git`

## 注意事项
1. 确保将SSH公钥添加到工蜂的SSH密钥设置中
2. SSH配置文件权限应为600
3. 如果遇到权限问题，检查IdentityFile路径是否正确

## 常见问题解决
1. "Connection refused" 错误：
   - 确保SSH隧道命令在本地机器上正在运行
   - 确保使用了正确的本地机器IP地址
   - 检查本地机器的防火墙设置（确保8022端口允许入站连接）
   - 确保git.woa.com的22端口是可访问的

2. 认证失败：
   - 确保服务器上的SSH密钥已添加到git.woa.com
   - 检查 `~/.ssh/config` 的权限设置

## 后续步骤
1. 根据实际网络环境选择合适的方案
2. 配置相应的SSH密钥
3. 测试连接是否成功
4. 确保Git操作正常进行 