from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .models import Hold, Metrics
from .utils import clear_hold_expiry, increment_metric

# Setup logging for tasks
logger = logging.getLogger(__name__)


@shared_task
def expire_specific_hold(hold_id):
    """
    Task to expire a specific hold at its exact expiry time
    """
    logger.info(f"Starting expire_specific_hold task for hold: {hold_id}")
    
    try:
        with transaction.atomic():
            # Get hold from database
            hold = Hold.objects.select_for_update().get(
                id=hold_id, 
                status=Hold.Status.ACTIVE
            )
            
            logger.info(f"Found hold {hold_id} with status: {hold.status}, expires at: {hold.expires_at}")
            
            # Check if actually expired
            if hold.is_expired:
                logger.info(f"Hold {hold_id} is expired, marking as EXPIRED")
                
                # Mark as expired
                hold.status = Hold.Status.EXPIRED
                hold.save(update_fields=['status', 'updated_at'])
                
                # Clear from Redis
                clear_hold_expiry(hold_id)
                
                # Update metrics
                metrics = Metrics.get_or_create_for_event(hold.event)
                metrics.update_metrics()
                
                # Increment Redis metrics
                increment_metric('holds_expired')
                increment_metric(f'holds_expired_event_{hold.event.id}')
                
                logger.info(
                    f"Hold expired successfully: {hold_id}",
                    extra={
                        'hold_id': hold_id,
                        'event_id': str(hold.event.id),
                        'qty': hold.qty,
                        'task': 'expire_specific_hold',
                    }
                )
            else:
                logger.warning(f"Hold {hold_id} is not expired yet, skipping. Expires at: {hold.expires_at}")
                
    except Hold.DoesNotExist:
        # Hold doesn't exist or already processed
        logger.warning(f"Hold not found in database: {hold_id}")
    except Exception as e:
        logger.error(f"Error expiring hold {hold_id}: {str(e)}", exc_info=True)
    
    logger.info(f"Completed expire_specific_hold task for hold: {hold_id}")



