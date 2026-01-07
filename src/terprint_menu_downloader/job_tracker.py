"""
Job Tracker for Menu Downloader
Tracks job progress in Azure SQL database to enable restart from failure point.
"""
import pyodbc
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Azure SQL Connection String
AZURE_SQL_CONNECTIONSTRING = "Driver={ODBC Driver 17 for SQL Server};Server=tcp:acidni-sql.database.windows.net,1433;Database=terprint;Uid=adm;Pwd=sql1234%;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"


class JobStatus(Enum):
    """Job status enum"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some items completed, some failed
    CANCELLED = "cancelled"


class StoreStatus(Enum):
    """Individual store download status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobTracker:
    """
    Tracks download job progress in Azure SQL database.
    Enables restart from failure point by tracking individual store status.
    """
    
    def __init__(self, connection_string: str = None, application_name: str = "MenuDownloader"):
        self.connection_string = connection_string or AZURE_SQL_CONNECTIONSTRING
        self.application_name = application_name
        self._ensure_tables_exist()
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get database connection"""
        return pyodbc.connect(self.connection_string)
    
    def _ensure_tables_exist(self):
        """Create job tracking tables if they don't exist"""
        create_jobs_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MenuDownloadJobs' AND xtype='U')
        CREATE TABLE MenuDownloadJobs (
            JobID UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
            JobName NVARCHAR(255) NOT NULL,
            ApplicationName NVARCHAR(100) NOT NULL DEFAULT 'MenuDownloader',
            StartTime DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
            EndTime DATETIME2 NULL,
            Status NVARCHAR(50) NOT NULL DEFAULT 'pending',
            TotalDispensaries INT NOT NULL DEFAULT 0,
            CompletedDispensaries INT NOT NULL DEFAULT 0,
            FailedDispensaries INT NOT NULL DEFAULT 0,
            TotalStores INT NOT NULL DEFAULT 0,
            CompletedStores INT NOT NULL DEFAULT 0,
            FailedStores INT NOT NULL DEFAULT 0,
            TotalProducts INT NOT NULL DEFAULT 0,
            TotalFilesUploaded INT NOT NULL DEFAULT 0,
            ErrorMessage NVARCHAR(MAX) NULL,
            Configuration NVARCHAR(MAX) NULL,
            CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
            UpdatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE()
        )
        """
        
        create_stores_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='MenuDownloadStores' AND xtype='U')
        CREATE TABLE MenuDownloadStores (
            StoreJobID UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
            JobID UNIQUEIDENTIFIER NOT NULL,
            Dispensary NVARCHAR(100) NOT NULL,
            StoreID NVARCHAR(255) NOT NULL,
            StoreName NVARCHAR(255) NULL,
            CategoryID NVARCHAR(100) NULL,
            Status NVARCHAR(50) NOT NULL DEFAULT 'pending',
            StartTime DATETIME2 NULL,
            EndTime DATETIME2 NULL,
            ProductCount INT NOT NULL DEFAULT 0,
            FileUploaded BIT NOT NULL DEFAULT 0,
            AzurePath NVARCHAR(1000) NULL,
            ErrorMessage NVARCHAR(MAX) NULL,
            RetryCount INT NOT NULL DEFAULT 0,
            CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
            UpdatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
            CONSTRAINT FK_MenuDownloadStores_Job FOREIGN KEY (JobID) REFERENCES MenuDownloadJobs(JobID)
        )
        """
        
        create_index = """
        IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_MenuDownloadStores_JobDispensary')
        CREATE INDEX IX_MenuDownloadStores_JobDispensary ON MenuDownloadStores(JobID, Dispensary, Status)
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_jobs_table)
                cursor.execute(create_stores_table)
                cursor.execute(create_index)
                conn.commit()
                logger.info("[OK] Job tracking tables verified/created")
        except Exception as e:
            logger.error(f"Error creating job tracking tables: {e}")
            raise
    
    def create_job(self, job_name: str, dispensaries: List[str], stores_config: Dict[str, List[str]], config: Dict = None) -> str:
        """
        Create a new download job and register all stores to be processed.
        
        Args:
            job_name: Name/description of the job
            dispensaries: List of dispensary IDs to process
            stores_config: Dict mapping dispensary ID to list of store IDs
            config: Optional configuration dict to store
            
        Returns:
            Job ID (UUID string)
        """
        job_id = str(uuid.uuid4())
        total_stores = sum(len(stores) for stores in stores_config.values())
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert job record
                cursor.execute("""
                    INSERT INTO MenuDownloadJobs 
                    (JobID, JobName, ApplicationName, Status, TotalDispensaries, TotalStores, Configuration)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    job_name,
                    self.application_name,
                    JobStatus.PENDING.value,
                    len(dispensaries),
                    total_stores,
                    json.dumps(config) if config else None
                ))
                
                # Insert store records for each dispensary
                for dispensary_id, store_ids in stores_config.items():
                    for store_id in store_ids:
                        # Handle store_id that might include category (e.g., "store_id:category_id")
                        if ':' in str(store_id):
                            parts = str(store_id).split(':')
                            actual_store_id = parts[0]
                            category_id = parts[1] if len(parts) > 1 else None
                        else:
                            actual_store_id = str(store_id)
                            category_id = None
                        
                        cursor.execute("""
                            INSERT INTO MenuDownloadStores 
                            (JobID, Dispensary, StoreID, CategoryID, Status)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            job_id,
                            dispensary_id,
                            actual_store_id,
                            category_id,
                            StoreStatus.PENDING.value
                        ))
                
                conn.commit()
                logger.info(f"[OK] Created job {job_id}: {job_name} with {total_stores} stores across {len(dispensaries)} dispensaries")
                
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            raise
        
        return job_id
    
    def start_job(self, job_id: str):
        """Mark job as in progress"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET Status = ?, StartTime = GETUTCDATE(), UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (JobStatus.IN_PROGRESS.value, job_id))
                conn.commit()
                logger.info(f"[OK] Job {job_id} started")
        except Exception as e:
            logger.error(f"Error starting job: {e}")
    
    def start_store(self, job_id: str, dispensary: str, store_id: str, category_id: str = None):
        """Mark a store as in progress"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if category_id:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, StartTime = GETUTCDATE(), UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ? AND CategoryID = ?
                    """, (StoreStatus.IN_PROGRESS.value, job_id, dispensary, store_id, category_id))
                else:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, StartTime = GETUTCDATE(), UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ?
                    """, (StoreStatus.IN_PROGRESS.value, job_id, dispensary, store_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error starting store {store_id}: {e}")
    
    def complete_store(self, job_id: str, dispensary: str, store_id: str, 
                       product_count: int, azure_path: str = None, category_id: str = None):
        """Mark a store as completed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if category_id:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, EndTime = GETUTCDATE(), ProductCount = ?, 
                            FileUploaded = 1, AzurePath = ?, UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ? AND CategoryID = ?
                    """, (StoreStatus.COMPLETED.value, product_count, azure_path, 
                          job_id, dispensary, store_id, category_id))
                else:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, EndTime = GETUTCDATE(), ProductCount = ?, 
                            FileUploaded = 1, AzurePath = ?, UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ?
                    """, (StoreStatus.COMPLETED.value, product_count, azure_path, 
                          job_id, dispensary, store_id))
                
                # Update job totals
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET CompletedStores = (SELECT COUNT(*) FROM MenuDownloadStores WHERE JobID = ? AND Status = ?),
                        TotalProducts = (SELECT ISNULL(SUM(ProductCount), 0) FROM MenuDownloadStores WHERE JobID = ?),
                        TotalFilesUploaded = (SELECT COUNT(*) FROM MenuDownloadStores WHERE JobID = ? AND FileUploaded = 1),
                        UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (job_id, StoreStatus.COMPLETED.value, job_id, job_id, job_id))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error completing store {store_id}: {e}")
    
    def fail_store(self, job_id: str, dispensary: str, store_id: str, 
                   error_message: str, category_id: str = None):
        """Mark a store as failed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if category_id:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, EndTime = GETUTCDATE(), ErrorMessage = ?, 
                            RetryCount = RetryCount + 1, UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ? AND CategoryID = ?
                    """, (StoreStatus.FAILED.value, error_message[:4000], 
                          job_id, dispensary, store_id, category_id))
                else:
                    cursor.execute("""
                        UPDATE MenuDownloadStores 
                        SET Status = ?, EndTime = GETUTCDATE(), ErrorMessage = ?, 
                            RetryCount = RetryCount + 1, UpdatedAt = GETUTCDATE()
                        WHERE JobID = ? AND Dispensary = ? AND StoreID = ?
                    """, (StoreStatus.FAILED.value, error_message[:4000], 
                          job_id, dispensary, store_id))
                
                # Update job failed count
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET FailedStores = (SELECT COUNT(*) FROM MenuDownloadStores WHERE JobID = ? AND Status = ?),
                        UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (job_id, StoreStatus.FAILED.value, job_id))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error failing store {store_id}: {e}")
    
    def complete_job(self, job_id: str, error_message: str = None):
        """Mark job as completed (or partial if there were failures or pending stores)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get job stats including pending stores
                cursor.execute("""
                    SELECT TotalStores, CompletedStores, FailedStores,
                           (SELECT COUNT(*) FROM MenuDownloadStores WHERE JobID = ? AND Status = 'pending') as PendingStores
                    FROM MenuDownloadJobs WHERE JobID = ?
                """, (job_id, job_id))
                row = cursor.fetchone()
                
                if row:
                    total, completed, failed, pending = row
                    # Determine status based on all store states
                    if pending > 0:
                        # If any stores are still pending, job is partial (not all stores processed)
                        status = JobStatus.PARTIAL.value
                        logger.warning(f"Job {job_id} has {pending} pending stores that were never processed")
                    elif failed > 0 and completed > 0:
                        status = JobStatus.PARTIAL.value
                    elif failed > 0 and completed == 0:
                        status = JobStatus.FAILED.value
                    elif completed == total and total > 0:
                        status = JobStatus.COMPLETED.value
                    else:
                        # No stores processed at all
                        status = JobStatus.PARTIAL.value
                else:
                    status = JobStatus.COMPLETED.value
                
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET Status = ?, EndTime = GETUTCDATE(), ErrorMessage = ?, UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (status, error_message, job_id))
                
                # Update dispensary counts
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET CompletedDispensaries = (
                        SELECT COUNT(DISTINCT Dispensary) FROM MenuDownloadStores 
                        WHERE JobID = ? AND Status = ?
                    ),
                    FailedDispensaries = (
                        SELECT COUNT(DISTINCT Dispensary) FROM MenuDownloadStores 
                        WHERE JobID = ? AND Status = ? 
                        AND Dispensary NOT IN (
                            SELECT DISTINCT Dispensary FROM MenuDownloadStores 
                            WHERE JobID = ? AND Status = ?
                        )
                    )
                    WHERE JobID = ?
                """, (job_id, StoreStatus.COMPLETED.value, 
                      job_id, StoreStatus.FAILED.value, 
                      job_id, StoreStatus.COMPLETED.value, job_id))
                
                conn.commit()
                logger.info(f"[OK] Job {job_id} completed with status: {status}")
                
        except Exception as e:
            logger.error(f"Error completing job: {e}")
    
    def fail_job(self, job_id: str, error_message: str):
        """Mark job as failed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET Status = ?, EndTime = GETUTCDATE(), ErrorMessage = ?, UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (JobStatus.FAILED.value, error_message[:4000], job_id))
                conn.commit()
                logger.info(f"[FAIL] Job {job_id} failed: {error_message[:100]}")
        except Exception as e:
            logger.error(f"Error failing job: {e}")
    
    def get_pending_stores(self, job_id: str, dispensary: str = None) -> List[Dict]:
        """Get list of pending stores for a job (for restart functionality)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if dispensary:
                    cursor.execute("""
                        SELECT StoreID, CategoryID, Dispensary, RetryCount
                        FROM MenuDownloadStores 
                        WHERE JobID = ? AND Dispensary = ? AND Status IN (?, ?)
                        ORDER BY CreatedAt
                    """, (job_id, dispensary, StoreStatus.PENDING.value, StoreStatus.FAILED.value))
                else:
                    cursor.execute("""
                        SELECT StoreID, CategoryID, Dispensary, RetryCount
                        FROM MenuDownloadStores 
                        WHERE JobID = ? AND Status IN (?, ?)
                        ORDER BY Dispensary, CreatedAt
                    """, (job_id, StoreStatus.PENDING.value, StoreStatus.FAILED.value))
                
                rows = cursor.fetchall()
                return [{
                    'store_id': row[0],
                    'category_id': row[1],
                    'dispensary': row[2],
                    'retry_count': row[3]
                } for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting pending stores: {e}")
            return []
    
    def get_incomplete_jobs(self, dispensary: str = None) -> List[Dict]:
        """Get list of incomplete jobs that can be resumed"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT j.JobID, j.JobName, j.StartTime, j.Status, 
                           j.TotalStores, j.CompletedStores, j.FailedStores,
                           j.TotalDispensaries
                    FROM MenuDownloadJobs j
                    WHERE j.Status IN (?, ?, ?)
                    ORDER BY j.StartTime DESC
                """, (JobStatus.IN_PROGRESS.value, JobStatus.PARTIAL.value, JobStatus.PENDING.value))
                
                rows = cursor.fetchall()
                return [{
                    'job_id': str(row[0]),
                    'job_name': row[1],
                    'start_time': row[2].isoformat() if row[2] else None,
                    'status': row[3],
                    'total_stores': row[4],
                    'completed_stores': row[5],
                    'failed_stores': row[6],
                    'total_dispensaries': row[7],
                    'pending_stores': row[4] - row[5] - row[6]
                } for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting incomplete jobs: {e}")
            return []
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get detailed status of a job"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT JobID, JobName, StartTime, EndTime, Status,
                           TotalDispensaries, CompletedDispensaries, FailedDispensaries,
                           TotalStores, CompletedStores, FailedStores,
                           TotalProducts, TotalFilesUploaded, ErrorMessage
                    FROM MenuDownloadJobs WHERE JobID = ?
                """, (job_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Get per-dispensary breakdown
                cursor.execute("""
                    SELECT Dispensary, 
                           COUNT(*) as Total,
                           SUM(CASE WHEN Status = ? THEN 1 ELSE 0 END) as Completed,
                           SUM(CASE WHEN Status = ? THEN 1 ELSE 0 END) as Failed,
                           SUM(CASE WHEN Status = ? THEN 1 ELSE 0 END) as Pending,
                           SUM(ProductCount) as Products
                    FROM MenuDownloadStores 
                    WHERE JobID = ?
                    GROUP BY Dispensary
                """, (StoreStatus.COMPLETED.value, StoreStatus.FAILED.value, 
                      StoreStatus.PENDING.value, job_id))
                
                dispensary_stats = {}
                for drow in cursor.fetchall():
                    dispensary_stats[drow[0]] = {
                        'total': drow[1],
                        'completed': drow[2],
                        'failed': drow[3],
                        'pending': drow[4],
                        'products': drow[5] or 0
                    }
                
                return {
                    'job_id': str(row[0]),
                    'job_name': row[1],
                    'start_time': row[2].isoformat() if row[2] else None,
                    'end_time': row[3].isoformat() if row[3] else None,
                    'status': row[4],
                    'total_dispensaries': row[5],
                    'completed_dispensaries': row[6],
                    'failed_dispensaries': row[7],
                    'total_stores': row[8],
                    'completed_stores': row[9],
                    'failed_stores': row[10],
                    'pending_stores': row[8] - row[9] - row[10],
                    'total_products': row[11],
                    'total_files_uploaded': row[12],
                    'error_message': row[13],
                    'dispensaries': dispensary_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
    
    def get_recent_jobs(self, limit: int = 10) -> List[Dict]:
        """Get list of recent jobs"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT TOP {limit} JobID, JobName, StartTime, EndTime, Status,
                           TotalStores, CompletedStores, FailedStores, TotalProducts
                    FROM MenuDownloadJobs 
                    ORDER BY StartTime DESC
                """)
                
                rows = cursor.fetchall()
                return [{
                    'job_id': str(row[0]),
                    'job_name': row[1],
                    'start_time': row[2].isoformat() if row[2] else None,
                    'end_time': row[3].isoformat() if row[3] else None,
                    'status': row[4],
                    'total_stores': row[5],
                    'completed_stores': row[6],
                    'failed_stores': row[7],
                    'total_products': row[8]
                } for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []
    
    def reset_failed_stores(self, job_id: str, max_retries: int = 3) -> int:
        """Reset failed stores to pending for retry (respecting max retries)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE MenuDownloadStores 
                    SET Status = ?, UpdatedAt = GETUTCDATE()
                    WHERE JobID = ? AND Status = ? AND RetryCount < ?
                """, (StoreStatus.PENDING.value, job_id, StoreStatus.FAILED.value, max_retries))
                
                reset_count = cursor.rowcount
                
                # Update job status back to in_progress
                cursor.execute("""
                    UPDATE MenuDownloadJobs 
                    SET Status = ?, UpdatedAt = GETUTCDATE()
                    WHERE JobID = ?
                """, (JobStatus.IN_PROGRESS.value, job_id))
                
                conn.commit()
                logger.info(f"[OK] Reset {reset_count} failed stores to pending for retry")
                return reset_count
                
        except Exception as e:
            logger.error(f"Error resetting failed stores: {e}")
            return 0
    
    def print_job_summary(self, job_id: str):
        """Print a formatted summary of job status"""
        status = self.get_job_status(job_id)
        if not status:
            print(f"Job {job_id} not found")
            return
        
        print("\n" + "=" * 70)
        print(f"JOB: {status['job_name']}")
        print(f"ID: {status['job_id']}")
        print(f"Status: {status['status'].upper()}")
        print("=" * 70)
        print(f"Started: {status['start_time']}")
        print(f"Ended:   {status['end_time'] or 'In Progress'}")
        print("-" * 70)
        print(f"Total Stores:     {status['total_stores']}")
        print(f"  + Completed:    {status['completed_stores']}")
        print(f"  x Failed:       {status['failed_stores']}")
        print(f"  o Pending:      {status['pending_stores']}")
        print(f"Total Products:   {status['total_products']}")
        print(f"Files Uploaded:   {status['total_files_uploaded']}")
        print("-" * 70)
        print("BY DISPENSARY:")
        for disp, stats in status.get('dispensaries', {}).items():
            pct = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"  {disp.upper():12} | {stats['completed']:3}/{stats['total']:3} ({pct:5.1f}%) | {stats['products']:5} products | {stats['failed']} failed")
        
        if status['error_message']:
            print("-" * 70)
            print(f"Error: {status['error_message'][:200]}")
        print("=" * 70 + "\n")


# Convenience function for quick status check
def check_job_status(job_id: str = None):
    """Quick function to check job status or list recent jobs"""
    tracker = JobTracker()
    
    if job_id:
        tracker.print_job_summary(job_id)
    else:
        print("\nRECENT JOBS:")
        print("-" * 80)
        jobs = tracker.get_recent_jobs(10)
        for job in jobs:
            pct = (job['completed_stores'] / job['total_stores'] * 100) if job['total_stores'] > 0 else 0
            status_icon = "+" if job['status'] == 'completed' else "x" if job['status'] == 'failed' else "o"
            print(f"{status_icon} {job['job_id'][:8]}... | {job['job_name'][:30]:30} | {job['status']:12} | {job['completed_stores']}/{job['total_stores']} ({pct:.0f}%)")
        
        # Show incomplete jobs
        incomplete = tracker.get_incomplete_jobs()
        if incomplete:
            print("\n[!] INCOMPLETE JOBS (can be resumed):")
            for job in incomplete:
                print(f"  -> {job['job_id']} | {job['pending_stores']} stores pending")


if __name__ == "__main__":
    import sys
    job_id = sys.argv[1] if len(sys.argv) > 1 else None
    check_job_status(job_id)
