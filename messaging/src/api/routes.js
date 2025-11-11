import { Router } from "express";
import chatsRouter from "./routes/chats.js";
import messagesRouter from "./routes/messages.js";
const apiRouter = Router();

apiRouter.use("/chats", chatsRouter);
apiRouter.use("/messages", messagesRouter);

/**
 * @swagger
 * /api/messaging/users:
 *   get:
 *     summary: Get all users from auth service with pagination support
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: query
 *         name: page
 *         schema:
 *           type: integer
 *           default: 1
 *         description: Page number for pagination
 *       - in: query
 *         name: page_size
 *         schema:
 *           type: integer
 *           default: 50
 *         description: Number of users per page (max 100)
 *       - in: query
 *         name: search
 *         schema:
 *           type: string
 *         description: Search term for filtering users by name or email
 *     responses:
 *       200:
 *         description: Paginated list of users from auth service
 *       401:
 *         description: Unauthorized
 *       500:
 *         description: Server error
 */
apiRouter.get("/users", async (req, res) => {
  try {
    const { page = 1, page_size = 50, search } = req.query;
    const authServiceUrl = process.env.AUTH_SERVICE_URL || 'http://localhost:9090/api/auth_service';

    // Build query parameters
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: Math.min(parseInt(page_size, 10) || 50, 100).toString(), // Max 100 per page
    });

    if (search) {
      params.append('search', search);
    }

    const response = await fetch(`${authServiceUrl}/api/user/users/?${params.toString()}`, {
      headers: {
        'Authorization': req.headers.authorization,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Auth service returned ${response.status}`);
    }

    const data = await response.json();

    // Transform the response to include only the fields we need for messaging
    const transformedData = {
      count: data.count,
      next: data.next,
      previous: data.previous,
      results: data.results.map(user => ({
        id: user.id,
        username: user.username,
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        role: user.role,
        job_role: user.job_role,
        tenant: user.tenant,
        status: user.status,
        online: false, // Default to offline, will be updated by presence system
        createdAt: user.createdAt || new Date().toISOString(),
        updatedAt: user.updatedAt || new Date().toISOString()
      }))
    };

    res.json(transformedData);
  } catch (error) {
    console.error('Error fetching users from auth service:', error);
    res.status(500).json({
      status: 'error',
      message: 'Failed to fetch users',
      error: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
});



export default apiRouter;
