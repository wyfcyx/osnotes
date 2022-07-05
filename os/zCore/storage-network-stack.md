# Storage Stack

## `sys_read`

```rust
// link of zCore: https://github.com/rcore-os/zCore
// zCore/linux-syscall/src/file/file.rs
impl Syscall<'_> {
    /// Reads from a specified file using a file descriptor. Before using this call,
    /// you must first obtain a file descriptor using the opensyscall. Returns bytes read successfully.
    /// - fd – file descriptor
    /// - base – pointer to the buffer to fill with read contents
    /// - len – number of bytes to read
    pub async fn sys_read(&self, fd: FileDesc, mut base: UserOutPtr<u8>, len: usize) -> SysResult {
        info!("read: fd={:?}, base={:?}, len={:#x}", fd, base, len);
        let proc = self.linux_process();

        // TODO wait a new struct to refactor
        if usize::from(fd) >= SOCKET_FD {
            let x = usize::from(fd);
            let socket = proc.get_socket(x)?;
            let mut buf = vec![0u8; len];
            let (len, _) = socket.lock().read(&mut buf).await;
            let len = len.unwrap_or(0);
            base.write_array(&buf[..len])?;
            Ok(len)
        } else {
            let file_like = proc.get_file_like(fd)?;
            let mut buf = vec![0u8; len];
            let len = file_like.read(&mut buf).await?;
            base.write_array(&buf[..len])?;
            Ok(len)
        }
    }
}

// we start from the filesystem side

// zCore/linux-object/src/process.rs
impl LinuxProcess {
    /// Get the `FileLike` with given `fd`.
    pub fn get_file_like(&self, fd: FileDesc) -> LxResult<Arc<dyn FileLike>> {
        let inner = self.inner.lock();
        trace!("get_file_like: {:#x?}", inner.files);
        inner.files.get(&fd).cloned().ok_or(LxError::EBADF)
    }
}

// definition of FileLike
// zCore/linux-object/src/fs/mod.rs
#[async_trait]
/// Generic file interface
///
/// - Normal file, Directory
/// - Socket
/// - Epoll instance
pub trait FileLike: KernelObject {
    /// Returns open flags.
    fn flags(&self) -> OpenFlags;
    /// Set open flags.
    fn set_flags(&self, f: OpenFlags) -> LxResult;
    /// Duplicate the file.
    fn dup(&self) -> Arc<dyn FileLike>;
    /// read to buffer
    async fn read(&self, buf: &mut [u8]) -> LxResult<usize>;
    /// write from buffer
    fn write(&self, buf: &[u8]) -> LxResult<usize>;
    /// read to buffer at given offset
    async fn read_at(&self, offset: u64, buf: &mut [u8]) -> LxResult<usize>;
    /// write from buffer at given offset
    fn write_at(&self, offset: u64, buf: &[u8]) -> LxResult<usize>;
    /// wait for some event on a file descriptor
    fn poll(&self) -> LxResult<PollStatus>;
    /// wait for some event on a file descriptor use async
    async fn async_poll(&self) -> LxResult<PollStatus>;
    /// manipulates the underlying device parameters of special files
    fn ioctl(&self, request: usize, arg1: usize, arg2: usize, arg3: usize) -> LxResult<usize>;
    /// Returns the [`VmObject`] representing the file with given `offset` and `len`.
    fn get_vmo(&self, offset: usize, len: usize) -> LxResult<Arc<VmObject>>;
}
```

`File` implements `FileLike` trait:

```rust
// zCore/linux-object/src/fs/file.rs

use rcore_fs::vfs::INode;

/// file inner mut data struct
#[derive(Clone)]
struct FileInner {
    /// content offset on read/write
    offset: u64,
    /// file open options
    flags: OpenFlags,
    /// file INode
    inode: Arc<dyn INode>,
}

/// file implement struct
pub struct File {
    /// object base
    base: KObjectBase,
    /// file path
    path: String,
    /// file inner mut data
    inner: RwLock<FileInner>,
}

#[async_trait]
impl FileLike for File {
	async fn read(&self, buf: &mut [u8]) -> LxResult<usize> {
        self.inner.write().read(buf).await
    }

    fn write(&self, buf: &[u8]) -> LxResult<usize> {
        self.inner.write().write(buf)
    }
}

impl FileInner {
    /// read from file
    async fn read(&mut self, buf: &mut [u8]) -> LxResult<usize> {
        let len = self.read_at(self.offset, buf).await?;
        self.offset += len as u64;
        Ok(len)
    }

    /// read from file at given offset
    async fn read_at(&mut self, offset: u64, buf: &mut [u8]) -> LxResult<usize> {
        if !self.flags.readable() {
            return Err(LxError::EBADF);
        }
        if !self.flags.non_block() {
            // block
            loop {
                match self.inode.read_at(offset as usize, buf) {
                    Ok(read_len) => return Ok(read_len),
                    Err(FsError::Again) => {
                        self.inode.async_poll().await?;
                    }
                    Err(err) => return Err(err.into()),
                }
            }
        }
        let len = self.inode.read_at(offset as usize, buf)?;
        Ok(len)
    }
}
```

Where is `INode::read_at`? Definition can be found here:

```rust
// https://github.com/rcore-os/rcore-fs/blob/master/rcore-fs/src/vfs.rs#L11
/// Abstract file system object such as file or directory.
pub trait INode: Any + Sync + Send {
    /// Read bytes at `offset` into `buf`, return the number of bytes read.
    fn read_at(&self, offset: usize, buf: &mut [u8]) -> Result<usize>;

    /// Write bytes at `offset` from `buf`, return the number of bytes written.
    fn write_at(&self, offset: usize, buf: &[u8]) -> Result<usize>;

    /// Poll the events, return a bitmap of events.
    fn poll(&self) -> Result<PollStatus>;

    /// Poll the events, return a bitmap of events, async version.
    /// Mention: this is not required!
    fn async_poll<'a>(
        &'a self,
    ) -> Pin<Box<dyn Future<Output = Result<PollStatus>> + Send + Sync + 'a>> {
        Box::pin(async move { self.poll() })
    }

    ...
}
```

All kinds of filesystems implement `INode` trait, take `SimpleFileSystem` as an example:

```rust
// https://github.com/rcore-os/rcore-fs/blob/master/rcore-fs-sfs/src/lib.rs#L407
impl vfs::INode for INodeImpl {
    fn read_at(&self, offset: usize, buf: &mut [u8]) -> vfs::Result<usize> {
        match self.disk_inode.read().type_ {
            FileType::File => self._read_at(offset, buf),
            FileType::SymLink => self._read_at(offset, buf),
            FileType::CharDevice => {
                let device_inodes = self.fs.device_inodes.read();
                let device_inode = device_inodes.get(&self.device_inode_id);
                match device_inode {
                    Some(device) => device.read_at(offset, buf),
                    None => Err(FsError::DeviceError),
                }
            }
            _ => Err(FsError::NotFile),
        }
    }
}

impl INodeImpl {
    /// Read content, no matter what type it is
    fn _read_at(&self, offset: usize, buf: &mut [u8]) -> vfs::Result<usize> {
        self._io_at(offset, offset + buf.len(), |device, range, offset| {
            device.read_block(
                range.block,
                range.begin,
                &mut buf[offset..offset + range.len()],
            )
        })
    }
}

// Where is the device from?

/// INode for SFS
pub struct INodeImpl {
    /// Reference to SFS, used by almost all operations
    fs: Arc<SimpleFileSystem>,
	...
}

/// filesystem for sfs
pub struct SimpleFileSystem {
    /// device
    device: Arc<dyn Device>,
	...
}

// device is of a type which implements the Device trait, which comes from:
// https://github.com/rcore-os/rcore-fs/blob/master/rcore-fs/src/dev/mod.rs#L11
/// Interface for FS to read & write
pub trait Device: Send + Sync {
    fn read_at(&self, offset: usize, buf: &mut [u8]) -> Result<usize>;
    fn write_at(&self, offset: usize, buf: &[u8]) -> Result<usize>;
    fn sync(&self) -> Result<()>;
}
// By the way, we also have a BlockDevice trait:
/// Device which can only R/W in blocks
pub trait BlockDevice: Send + Sync {
    const BLOCK_SIZE_LOG2: u8;
    fn read_at(&self, block_id: BlockId, buf: &mut [u8]) -> Result<()>;
    fn write_at(&self, block_id: BlockId, buf: &[u8]) -> Result<()>;
    fn sync(&self) -> Result<()>;
}
// We implement Device trait for types which have already implemented BlockDevice trait
impl<T: BlockDevice> Device for T {
	...
}
```

However, who implements the `BlockDevice`? In other words, where is the real block device driver code? 

zCore open its root filesystem on initialization:

```rust
// https://github.com/rcore-os/zCore/blob/master/zCore/src/main.rs#L46
// then https://github.com/rcore-os/zCore/blob/master/zCore/src/fs.rs#L16
#[cfg(not(feature = "libos"))]
pub fn rootfs() -> Arc<dyn FileSystem> {
    use linux_object::fs::rcore_fs_wrapper::{Block, BlockCache, MemBuf};
    use rcore_fs::dev::Device;

    let device: Arc<dyn Device> = if let Some(initrd) = init_ram_disk() {
        Arc::new(MemBuf::new(initrd))
    } else {
        let block = kernel_hal::drivers::all_block().first_unwrap();
        Arc::new(BlockCache::new(Block::new(block), 0x100))
    };
    info!("Opening the rootfs...");
    rcore_fs_sfs::SimpleFileSystem::open(device).expect("failed to open device SimpleFS")
}
```

Unfortunately, currently the block device is a RAM disk rather than VirtIO-blk on x86_64 platform:

```rust
// https://github.com/rcore-os/zCore/blob/master/linux-object/src/fs/rcore_fs_wrapper.rs#L15
/// Memory buffer for device.
pub struct MemBuf(RwLock<&'static mut [u8]>);

impl MemBuf {
    /// create a [`MemBuf`] struct.
    pub fn new(buf: &'static mut [u8]) -> Self {
        MemBuf(RwLock::new(buf))
    }
}

impl Device for MemBuf {
    fn read_at(&self, offset: usize, buf: &mut [u8]) -> Result<usize> {
        let slice = self.0.read();
        let len = buf.len().min(slice.len() - offset);
        buf[..len].copy_from_slice(&slice[offset..offset + len]);
        Ok(len)
    }
    fn write_at(&self, offset: usize, buf: &[u8]) -> Result<usize> {
        let mut slice = self.0.write();
        let len = buf.len().min(slice.len() - offset);
        slice[offset..offset + len].copy_from_slice(&buf[..len]);
        Ok(len)
    }
    fn sync(&self) -> Result<()> {
        Ok(())
    }
}
```

What if the block device is a VirtIO-blk? On an aarch64 platform:

```rust
// https://github.com/rcore-os/zCore/blob/master/kernel-hal/src/bare/arch/aarch64/drivers.rs#L29
use zcore_drivers::virtio::{VirtIOHeader, VirtIoBlk};
use zcore_drivers::Device;
pub fn init() {
    if cfg!(not(feature = "link-user-img")) {
        let virtio_blk = Arc::new(
            VirtIoBlk::new(unsafe { &mut *(phys_to_virt(VIRTIO_BASE) as *mut VirtIOHeader) })
                .unwrap(),
        );
        drivers::add_device(Device::Block(virtio_blk));
    }
}

// VirtIoBlk is just a wrapper of another type provide by the virtio_drivers library
// https://github.com/rcore-os/zCore/blob/master/drivers/src/virtio/blk.rs#L2
use virtio_drivers::{VirtIOBlk as InnerDriver, VirtIOHeader};
pub struct VirtIoBlk<'a> {
    inner: Mutex<InnerDriver<'a>>,
}

// however, virtio_drivers only provides sync implementation
```

# Networking Stack

### Socket

```rust
// link of zCore: https://github.com/rcore-os/zCore
// zCore/linux-syscall/src/file/file.rs
impl Syscall<'_> {
    /// Reads from a specified file using a file descriptor. Before using this call,
    /// you must first obtain a file descriptor using the opensyscall. Returns bytes read successfully.
    /// - fd – file descriptor
    /// - base – pointer to the buffer to fill with read contents
    /// - len – number of bytes to read
    pub async fn sys_read(&self, fd: FileDesc, mut base: UserOutPtr<u8>, len: usize) -> SysResult {
        info!("read: fd={:?}, base={:?}, len={:#x}", fd, base, len);
        let proc = self.linux_process();

        // TODO wait a new struct to refactor
        if usize::from(fd) >= SOCKET_FD {
            let x = usize::from(fd);
            let socket = proc.get_socket(x)?;
            let mut buf = vec![0u8; len];
            let (len, _) = socket.lock().read(&mut buf).await;
            let len = len.unwrap_or(0);
            base.write_array(&buf[..len])?;
            Ok(len)
        } else {
            let file_like = proc.get_file_like(fd)?;
            let mut buf = vec![0u8; len];
            let len = file_like.read(&mut buf).await?;
            base.write_array(&buf[..len])?;
            Ok(len)
        }
    }
}

// zCore/linux-object/src/process.rs
impl LinuxProcess {
    /// Get the `Socket` with given `fd`.
    pub fn get_socket(&self, fd: usize) -> LxResult<Arc<Mutex<dyn Socket>>> {
        // unimplemented!()
        let inner = self.inner.lock();
        let socket = inner.sockets.get(&fd).cloned().ok_or(LxError::EBADF);
        socket
    }
}

// definition of the Socket trait
// zCore/linux-object/src/net/mod.rs
/// Common methods that a socket must have
#[async_trait]
pub trait Socket: Send + Sync + Debug {
    /// missing documentation
    async fn read(&self, data: &mut [u8]) -> (SysResult, Endpoint);
    /// missing documentation
    fn write(&self, data: &[u8], sendto_endpoint: Option<Endpoint>) -> SysResult;
    /// missing documentation
    fn poll(&self) -> (bool, bool, bool); // (in, out, err)
    /// missing documentation
    async fn connect(&mut self, endpoint: Endpoint) -> SysResult;
    /// missing documentation
    fn bind(&mut self, _endpoint: Endpoint) -> SysResult {
        Err(LxError::EINVAL)
    }
    /// missing documentation
    fn listen(&mut self) -> SysResult {
        Err(LxError::EINVAL)
    }
    /// missing documentation
    fn shutdown(&self) -> SysResult {
        Err(LxError::EINVAL)
    }
    /// missing documentation
    async fn accept(&mut self) -> LxResult<(Arc<Mutex<dyn Socket>>, Endpoint)> {
        Err(LxError::EINVAL)
    }
    /// missing documentation
    fn endpoint(&self) -> Option<Endpoint> {
        None
    }
    /// missing documentation
    fn remote_endpoint(&self) -> Option<Endpoint> {
        None
    }
    /// missing documentation
    fn setsockopt(&mut self, _level: usize, _opt: usize, _data: &[u8]) -> SysResult {
        warn!("setsockopt is unimplemented");
        Ok(0)
    }
    /// missing documentation
    fn ioctl(&self, _request: usize, _arg1: usize, _arg2: usize, _arg3: usize) -> SysResult {
        warn!("ioctl is unimplemented for this socket");
        Ok(0)
    }
    /// missing documentation
    fn fcntl(&self, _cmd: usize, _arg: usize) -> SysResult {
        warn!("ioctl is unimplemented for this socket");
        Ok(0)
    }
}

// TcpSocketState & UdpSocketState & NetlinkSocketState implement Socket trait
// but they use busy looping to implement async fn, for example:
impl Socket for TcpSocketState {
    /// read to buffer
    async fn read(&self, data: &mut [u8]) -> (SysResult, Endpoint) {
        info!("tcp read");
        loop {
            poll_ifaces();
            let net_sockets = get_sockets();
            let mut sockets = net_sockets.lock();
            let mut socket = sockets.get::<TcpSocket>(self.handle.0);
            if socket.may_recv() {
                if let Ok(size) = socket.recv_slice(data) {
                    if size > 0 {
                        let endpoint = socket.remote_endpoint();
                        // avoid deadlock
                        drop(socket);
                        drop(sockets);
                        poll_ifaces();
                        return (Ok(size), Endpoint::Ip(endpoint));
                    }
                }
            } else {
                return (
                    Err(LxError::ENOTCONN),
                    Endpoint::Ip(IpEndpoint::UNSPECIFIED),
                );
            }
        }
    }
}

// as we mentioned before, nic driver implementation support interrupts
```

